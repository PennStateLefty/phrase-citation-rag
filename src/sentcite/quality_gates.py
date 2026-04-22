"""Quality gates for attribution-first synthetic GT.

Two gates run, in order, against the output of :mod:`sentcite.synth_gt`:

1. **Agreement filter.** A *different* model than the synth-GT author
   (the judge role — the third distinct model in the stack) independently
   evaluates each ``(question, span, gold_answer)`` triple. An item passes
   iff the judge reports the question is well-formed *and* the answer is
   strictly supported by the span, with no outside facts.

2. **Union labeler.** For each passing item, we search the Layout Y
   ``tax-sentences`` index with the gold answer as the query and hand the
   judge a candidate pool. The judge returns the indices of candidates
   that independently support the answer. Those ``sentence_id``\\s are
   merged into every per-answer-sentence list in ``gold_citations``,
   reducing false-negative recall on the evaluation harness.

Both gates run under the same three-distinct-models invariant used by
:mod:`sentcite.synth_gt` (enforced by
:func:`sentcite.llm.get_binding`). Items that fail the agreement filter
are kept in the output with ``judge_*`` flags set to ``False`` so the
manifest can explain why counts dropped.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.search.documents import SearchClient

from .config import AzureConfig
from .indexing import embed_texts
from .llm import get_binding, get_client, get_model_id
from .retrieval import search_sentences
from .schema import GroundTruthItem
from .synth_gt import _parse_model_json  # reuse tolerant JSON extractor


# ---------------------------------------------------------------------------
# Span reconstitution from local chunk corpus
# ---------------------------------------------------------------------------


def build_sentence_lookup(chunks: Iterable[dict]) -> dict[str, dict]:
    """Flatten corpus chunks into ``{sentence_id: sentence_dict}``.

    Each value carries at least ``text``, ``chunk_id``, ``document_id``,
    ``page``, and ``section_path`` — enough to reconstruct span text and
    to provide the judge with context labels.
    """
    out: dict[str, dict] = {}
    for chunk in chunks:
        for s in chunk.get("sentences") or []:
            sid = s.get("sentence_id")
            if sid and sid not in out:
                out[sid] = s
    return out


def reconstruct_span_text(
    sentence_ids: Sequence[str], lookup: dict[str, dict]
) -> str:
    """Join the given sentence_ids' text in order. Silently drops unknown ids."""
    parts = [lookup[sid].get("text", "").strip() for sid in sentence_ids if sid in lookup]
    return " ".join(p for p in parts if p).strip()


# ---------------------------------------------------------------------------
# Agreement filter
# ---------------------------------------------------------------------------


AGREEMENT_SYSTEM = """You audit synthetic evaluation items for an IRS \
tax-audit AI system.

You receive: a SOURCE SPAN (1-3 sentences from an IRS publication), a \
QUESTION, and a GOLD ANSWER proposed by another model. Your job is to \
decide, strictly, whether this item is usable for evaluation.

Return ONLY a JSON object with this exact shape and nothing else:

{
  "well_formed": true|false,
  "supported": true|false,
  "reasons": "<one sentence explanation>"
}

Rules:
- well_formed = the question is specific, unambiguous, and auditor-style \
(not trivial, not about the publication's formatting). A reader given the \
span alone should know what is being asked.
- supported = every factual claim in GOLD ANSWER is directly entailed by \
the SPAN. Outside knowledge, paraphrased facts not present in the span, \
invented numbers, or claims the span only hints at must be flagged as \
unsupported.
- Be conservative. When in doubt, return false with a short reason.
- Do not include code fences or prose outside the JSON object."""


AGREEMENT_USER = """SPAN (document={document_id}, page={page}):
\"\"\"
{span_text}
\"\"\"

QUESTION:
{question}

GOLD ANSWER:
{gold_answer}

Return the JSON object now."""


@dataclass
class AgreementVerdict:
    well_formed: bool
    supported: bool
    reasons: str


def _coerce_bool(val, field: str) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "yes", "1"):
            return True
        if v in ("false", "no", "0"):
            return False
    raise ValueError(f"judge did not return a boolean for {field!r}: {val!r}")


def judge_agreement(
    item: GroundTruthItem,
    span_text: str,
    *,
    client: ChatCompletionsClient,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 200,
) -> AgreementVerdict:
    user = AGREEMENT_USER.format(
        document_id=item.document_id or "",
        page=item.page if item.page is not None else "",
        span_text=span_text,
        question=item.question,
        gold_answer=item.gold_answer,
    )
    resp = client.complete(
        model=model,
        messages=[
            SystemMessage(content=AGREEMENT_SYSTEM),
            UserMessage(content=user),
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = (resp.choices[0].message.content or "").strip()
    obj = _parse_model_json(content)
    return AgreementVerdict(
        well_formed=_coerce_bool(obj.get("well_formed"), "well_formed"),
        supported=_coerce_bool(obj.get("supported"), "supported"),
        reasons=(obj.get("reasons") or "").strip()[:500],
    )


# ---------------------------------------------------------------------------
# Union labeler
# ---------------------------------------------------------------------------


UNION_SYSTEM = """You determine which additional source sentences \
independently support a given ANSWER.

You receive: a QUESTION, an ANSWER, and a numbered list of CANDIDATE \
sentences drawn from the same IRS corpus. Return ONLY a JSON object with \
this exact shape and nothing else:

{
  "supporting_indices": [<ints>],
  "reasons": "<one sentence>"
}

Rules:
- A candidate 'supports' the ANSWER if, read on its own, it directly \
entails at least one specific factual claim in the ANSWER (the same \
rule, same number, same definition, or a clear restatement). Do NOT \
include candidates that are only topically related.
- Exclude candidates that merely repeat the QUESTION's topic without \
entailing a claim in the ANSWER.
- Output indices are 0-based, strictly a subset of the candidate \
indices shown. If no candidate qualifies, return [].
- Do not include code fences or prose outside the JSON object."""


UNION_USER = """QUESTION:
{question}

ANSWER:
{answer}

CANDIDATE SENTENCES:
{candidates}

Return the JSON object now."""


@dataclass
class UnionLabelResult:
    additions: list[str]
    considered: int
    kept: int
    reasons: str


def _format_candidates(candidates: list[dict]) -> str:
    lines = []
    for i, c in enumerate(candidates):
        section = " > ".join(c.get("section_path") or []) or "(root)"
        text = (c.get("text") or "").strip().replace("\n", " ")
        lines.append(
            f"[{i}] (doc={c.get('document_id')}, p{c.get('page')}, {section}) {text}"
        )
    return "\n".join(lines)


def _select_union_candidates(
    item: GroundTruthItem,
    *,
    cfg: AzureConfig,
    search_client: SearchClient | None = None,
    answer_embedding: list[float] | None = None,
    top_k: int = 20,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """Pull the top_k sentence candidates that are likely to support the answer."""
    if answer_embedding is None:
        vec = embed_texts([item.gold_answer], cfg=cfg)[0]
    else:
        vec = answer_embedding
    hits = search_sentences(
        item.gold_answer,
        vec,
        cfg=cfg,
        top_k=top_k,
        client=search_client,
    )
    exclude = exclude_ids or set(item.source_span_sentence_ids)
    return [h for h in hits if h.get("sentence_id") not in exclude]


def label_union_supports(
    item: GroundTruthItem,
    candidates: list[dict],
    *,
    client: ChatCompletionsClient,
    model: str,
    max_candidates: int = 10,
    temperature: float = 0.0,
    max_tokens: int = 300,
) -> UnionLabelResult:
    pool = candidates[:max_candidates]
    if not pool:
        return UnionLabelResult(additions=[], considered=0, kept=0, reasons="no candidates")
    user = UNION_USER.format(
        question=item.question,
        answer=item.gold_answer,
        candidates=_format_candidates(pool),
    )
    resp = client.complete(
        model=model,
        messages=[SystemMessage(content=UNION_SYSTEM), UserMessage(content=user)],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = (resp.choices[0].message.content or "").strip()
    try:
        obj = _parse_model_json(content)
    except ValueError:
        return UnionLabelResult(
            additions=[],
            considered=len(pool),
            kept=0,
            reasons=f"judge returned unparseable content: {content[:200]!r}",
        )
    raw_indices = obj.get("supporting_indices") or []
    keep_ids: list[str] = []
    seen: set[str] = set()
    for v in raw_indices:
        try:
            i = int(v)
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(pool):
            sid = pool[i].get("sentence_id")
            if sid and sid not in seen:
                keep_ids.append(sid)
                seen.add(sid)
    return UnionLabelResult(
        additions=keep_ids,
        considered=len(pool),
        kept=len(keep_ids),
        reasons=(obj.get("reasons") or "").strip()[:500],
    )


# ---------------------------------------------------------------------------
# Merge additions back into an item
# ---------------------------------------------------------------------------


def _merge_union_into_item(item: GroundTruthItem, additions: list[str]) -> GroundTruthItem:
    if not additions:
        return item
    new_gc: list[list[str]] = []
    for cites in item.gold_citations:
        seen = set(cites)
        merged = list(cites)
        for sid in additions:
            if sid not in seen:
                merged.append(sid)
                seen.add(sid)
        new_gc.append(merged)
    data = item.model_dump()
    data["gold_citations"] = new_gc
    data["union_additions"] = list({*item.union_additions, *additions})
    return GroundTruthItem(**data)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class QualityGateRun:
    items: list[GroundTruthItem]
    rag_model: str
    synth_model: str
    judge_model: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    agreement_passed: int
    agreement_failed: int
    union_additions_total: int
    # Per-item agreement failures, for manifest drill-down.
    failures: list[dict]

    def to_manifest(self) -> dict:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "rag_model": self.rag_model,
            "synth_model": self.synth_model,
            "judge_model": self.judge_model,
            "total_items": len(self.items),
            "agreement_passed": self.agreement_passed,
            "agreement_failed": self.agreement_failed,
            "union_additions_total": self.union_additions_total,
        }


def run_quality_gates(
    items: Sequence[GroundTruthItem],
    chunks: Iterable[dict],
    *,
    cfg: AzureConfig | None = None,
    judge_client: ChatCompletionsClient | None = None,
    search_client: SearchClient | None = None,
    top_k_candidates: int = 20,
    max_candidates_to_judge: int = 10,
    skip_union_if_agreement_fails: bool = True,
    on_progress=None,
) -> QualityGateRun:
    cfg = cfg or AzureConfig.from_env()
    judge_binding = get_binding("judge", cfg)
    synth_binding = get_binding("synth_gt", cfg)
    rag_binding = get_binding("rag", cfg)
    judge_client = judge_client or get_client("judge", cfg)
    judge_model = get_model_id("judge", cfg)

    # Guard: a synth-GT item's author_model must not equal the judge model.
    # get_binding enforces three-distinct-models globally, but a loaded items.jsonl
    # could have been authored under a prior configuration. Flag, don't silently mix.
    for it in items:
        if it.author_model and it.author_model.lower() == judge_binding.model_identity.lower():
            raise RuntimeError(
                f"contamination guard: item {it.question_id} was authored by "
                f"{it.author_model!r} which matches the current judge "
                f"{judge_binding.model_identity!r}. Reconfigure the judge role "
                "so the synth-GT author and judge are distinct."
            )

    lookup = build_sentence_lookup(chunks)

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    out: list[GroundTruthItem] = []
    failures: list[dict] = []
    passed = 0
    total_additions = 0
    for idx, item in enumerate(items):
        span_text = reconstruct_span_text(item.source_span_sentence_ids, lookup)
        # --- Agreement filter ---
        try:
            verdict = judge_agreement(item, span_text, client=judge_client, model=judge_model)
        except Exception as exc:  # noqa: BLE001
            verdict = AgreementVerdict(
                well_formed=False,
                supported=False,
                reasons=f"judge_agreement error: {type(exc).__name__}: {exc}",
            )
        item = _set_verdict(item, verdict, judge_binding.model_identity)
        agreement_ok = verdict.well_formed and verdict.supported
        if agreement_ok:
            passed += 1
        else:
            failures.append(
                {
                    "question_id": item.question_id,
                    "well_formed": verdict.well_formed,
                    "supported": verdict.supported,
                    "reasons": verdict.reasons,
                }
            )

        # --- Union labeler ---
        if agreement_ok or not skip_union_if_agreement_fails:
            try:
                candidates = _select_union_candidates(
                    item, cfg=cfg, search_client=search_client, top_k=top_k_candidates
                )
                union_res = label_union_supports(
                    item,
                    candidates,
                    client=judge_client,
                    model=judge_model,
                    max_candidates=max_candidates_to_judge,
                )
                item = _merge_union_into_item(item, union_res.additions)
                total_additions += union_res.kept
            except Exception as exc:  # noqa: BLE001
                # Don't lose the item - just record the union-labeler failure.
                failures.append(
                    {
                        "question_id": item.question_id,
                        "stage": "union_labeler",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        out.append(item)
        if on_progress is not None:
            on_progress(idx + 1, len(items), passed, total_additions)

    finished = datetime.now(timezone.utc)
    return QualityGateRun(
        items=out,
        rag_model=rag_binding.model_identity,
        synth_model=synth_binding.model_identity,
        judge_model=judge_binding.model_identity,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        elapsed_seconds=time.perf_counter() - t0,
        agreement_passed=passed,
        agreement_failed=len(items) - passed,
        union_additions_total=total_additions,
        failures=failures,
    )


def _set_verdict(
    item: GroundTruthItem, verdict: AgreementVerdict, judge_model: str
) -> GroundTruthItem:
    data = item.model_dump()
    data["judge_model"] = judge_model
    data["judge_well_formed"] = verdict.well_formed
    data["judge_supported"] = verdict.supported
    data["judge_reasons"] = verdict.reasons
    return GroundTruthItem(**data)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def write_quality_gate_run(
    run: QualityGateRun,
    *,
    out_dir: Path | str,
    run_id: str | None = None,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    items_path = run_dir / "items_reviewed.jsonl"
    with items_path.open("w", encoding="utf-8") as f:
        for it in run.items:
            f.write(it.model_dump_json() + "\n")

    failures_path = run_dir / "qg_failures.jsonl"
    with failures_path.open("w", encoding="utf-8") as f:
        for fail in run.failures:
            f.write(json.dumps(fail) + "\n")

    manifest_path = run_dir / "manifest.json"
    manifest = run.to_manifest()
    manifest["run_id"] = run_id
    manifest["items_path"] = str(items_path)
    manifest["failures_path"] = str(failures_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {"items": items_path, "failures": failures_path, "manifest": manifest_path}
