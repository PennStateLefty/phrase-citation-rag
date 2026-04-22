"""Attribution-first synthetic ground-truth generator.

**Why this exists**

Phase 1a of the sentence-citation prototype must be SME-free. To evaluate
recall / precision of sentence-level citations we need questions with known
gold citations. Rather than ask a model to cite its own work (which
contaminates the signal), we invert the process:

    1. Pick a known *source span* from the corpus (1–3 consecutive sentences
       within the same chunk). Its ``sentence_id``\\s are the gold citations
       *by construction*.
    2. Ask a foundation model from a **different family than the RAG
       generator** to propose an auditor-style question + gold answer whose
       only faithful support is that span.
    3. Record provenance (which model authored which item) so downstream
       eval code can audit for same-family contamination.

The runtime invariant that RAG / synth-GT / judge are three distinct model
identities is enforced by :meth:`sentcite.config.AzureConfig.assert_three_distinct_models`,
which is invoked on every call to :func:`sentcite.llm.get_binding`.

The output of this module is consumed by:

* ``synth-gt-quality-gates`` (cross-model agreement + union labeler), which
  expands ``source_span_sentence_ids`` with any other corpus sentences that
  also support the gold answer, reducing false-negatives on recall.
* The evaluation harness, which converts each item into per-answer-sentence
  gold citations by pairing the model's split of ``gold_answer`` with
  ``source_span_sentence_ids``.
"""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, Sequence

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage

from .chunking import split_sentences
from .config import AzureConfig
from .llm import get_binding, get_client, get_model_id
from .schema import GroundTruthItem

Difficulty = Literal["easy", "medium", "hard"]
_DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")


# ---------------------------------------------------------------------------
# Span selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Span:
    """A contiguous slice of sentences inside a single chunk.

    ``sentence_ids`` are the attribution-first gold citations for any
    question/answer the LLM produces from ``text``.
    """

    document_id: str
    chunk_id: str
    page: int
    section_path: tuple[str, ...]
    sentence_ids: tuple[str, ...]
    text: str
    difficulty: Difficulty


_DIGIT_RE = re.compile(r"\d")


def _classify_difficulty(sentences: Sequence[dict]) -> Difficulty:
    """Heuristic: 1 numeric/short sentence is easy; 2-sent factual = medium; 3 = hard."""
    n = len(sentences)
    if n >= 3:
        return "hard"
    if n == 2:
        return "medium"
    # n == 1
    s = sentences[0].get("text", "") or ""
    if _DIGIT_RE.search(s) or len(s) < 120:
        return "easy"
    return "medium"


def _load_chunks_from_path(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_corpus_chunks(chunk_dir: Path | str = "data/chunks") -> list[dict]:
    """Load every chunk JSONL file under ``chunk_dir`` into a flat list."""
    chunk_dir = Path(chunk_dir)
    chunks: list[dict] = []
    for p in sorted(chunk_dir.glob("*.jsonl")):
        chunks.extend(_load_chunks_from_path(p))
    return chunks


def _enumerate_spans(chunk: dict, *, max_span_len: int = 3) -> list[Span]:
    """All contiguous 1..max_span_len sentence runs inside a single chunk."""
    sents = chunk.get("sentences") or []
    if not sents:
        return []
    doc_id = chunk["document_id"]
    chunk_id = chunk["chunk_id"]
    page = int(chunk.get("page", 0) or 0)
    section = tuple(chunk.get("section_path") or [])
    spans: list[Span] = []
    for i in range(len(sents)):
        for L in range(1, max_span_len + 1):
            j = i + L
            if j > len(sents):
                break
            window = sents[i:j]
            text = " ".join((s.get("text") or "").strip() for s in window).strip()
            if not text:
                continue
            spans.append(
                Span(
                    document_id=doc_id,
                    chunk_id=chunk_id,
                    page=page,
                    section_path=section,
                    sentence_ids=tuple(s["sentence_id"] for s in window),
                    text=text,
                    difficulty=_classify_difficulty(window),
                )
            )
    return spans


def select_spans(
    chunks: Iterable[dict],
    *,
    target_per_difficulty: dict[Difficulty, int] | None = None,
    max_spans_per_chunk: int = 1,
    max_span_len: int = 3,
    seed: int = 7,
) -> list[Span]:
    """Difficulty-stratified random sample of spans across the corpus.

    Defaults target 100 total items (easy=40, medium=35, hard=25), capping at
    one span per chunk to avoid over-representing long documents. If a
    difficulty class can't meet its quota the shortfall is logged via the
    returned list length — callers should compare against the requested
    totals if strict counts matter.
    """
    target = target_per_difficulty or {"easy": 40, "medium": 35, "hard": 25}

    rng = random.Random(seed)
    pool_by_diff: dict[Difficulty, list[Span]] = {d: [] for d in _DIFFICULTIES}
    # One span per chunk, chosen uniformly from that chunk's enumerated spans
    # of the correct difficulty. Simpler + fair across documents.
    chunks_list = list(chunks)
    rng.shuffle(chunks_list)
    for chunk in chunks_list:
        spans = _enumerate_spans(chunk, max_span_len=max_span_len)
        if not spans:
            continue
        rng.shuffle(spans)
        taken = 0
        # Offer at most one span per difficulty per chunk, up to max_spans_per_chunk.
        for span in spans:
            if taken >= max_spans_per_chunk:
                break
            if len(pool_by_diff[span.difficulty]) >= target.get(span.difficulty, 0):
                continue
            pool_by_diff[span.difficulty].append(span)
            taken += 1

    # Flatten and reshuffle so notebook output isn't clumped by difficulty.
    out: list[Span] = []
    for d in _DIFFICULTIES:
        out.extend(pool_by_diff[d])
    rng.shuffle(out)
    return out


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """You author evaluation items for a tax-auditing AI system.

You are given ONE SOURCE SPAN (1-3 consecutive sentences from an IRS \
publication). Produce a single JSON object with this exact shape and \
nothing else:

{
  "question": "<auditor-style question>",
  "gold_answer": "<1-3 sentence answer, strictly supported by the SPAN>",
  "rationale": "<one sentence explaining how the SPAN supports the answer>"
}

Hard rules:
- The question must be answerable ONLY from the SPAN. A reader without the \
SPAN (including someone with general tax knowledge) should not be able to \
answer it confidently.
- Every factual claim in gold_answer MUST be directly supported by the SPAN. \
Do not introduce outside facts, numbers, or regulations.
- Do NOT include citations, footnotes, or [s:...] markers in gold_answer.
- Prefer specific, concrete auditor questions ("What records must a sole \
proprietor keep for employment taxes?") over vague ones ("What is this \
about?").
- Match the requested DIFFICULTY:
    easy   = single-fact lookup (one number, date, name, or short rule).
    medium = short rule or two connected facts.
    hard   = multi-step reasoning across all sentences in the SPAN.
- Output the JSON object only. No prose before or after. No code fences."""


USER_TEMPLATE = """DIFFICULTY: {difficulty}

SPAN (document={document_id}, page={page}, section={section}):
\"\"\"
{span_text}
\"\"\"

Return the JSON object now."""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_model_json(content: str) -> dict:
    """Best-effort JSON object extraction from a chat completion content string.

    Handles:
    - plain JSON
    - ```json ... ``` fenced blocks
    - prose-wrapped JSON (finds the first {...} block)
    """
    if not content:
        raise ValueError("empty model response")
    s = content.strip()
    # strip fences
    s = _CODE_FENCE_RE.sub("", s).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = _JSON_OBJECT_RE.search(s)
        if not m:
            raise ValueError(f"no JSON object in response: {content[:200]!r}") from None
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError(f"expected JSON object, got {type(obj).__name__}")
    return obj


def _validate_item_fields(obj: dict) -> tuple[str, str]:
    q = (obj.get("question") or "").strip()
    a = (obj.get("gold_answer") or "").strip()
    if not q:
        raise ValueError("model returned empty question")
    if not a:
        raise ValueError("model returned empty gold_answer")
    return q, a


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


@dataclass
class SynthGTFailure:
    span_chunk_id: str
    span_sentence_ids: tuple[str, ...]
    difficulty: Difficulty
    error: str


@dataclass
class SynthGTRun:
    items: list[GroundTruthItem]
    failures: list[SynthGTFailure]
    author_model: str
    rag_model: str
    judge_model: str
    started_at: str
    finished_at: str
    seed: int
    target_counts: dict[str, int]
    elapsed_seconds: float

    def to_manifest(self) -> dict:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "seed": self.seed,
            "target_counts": self.target_counts,
            "author_model": self.author_model,
            "rag_model": self.rag_model,
            "judge_model": self.judge_model,
            "total_items": len(self.items),
            "total_failures": len(self.failures),
            "difficulty_counts": {
                d: sum(1 for it in self.items if it.difficulty == d)
                for d in _DIFFICULTIES
            },
        }


def _question_id(span: Span, *, seq: int) -> str:
    return f"synth-{seq:04d}-{span.chunk_id}"


def _build_item(
    *,
    span: Span,
    question: str,
    gold_answer: str,
    author_model: str,
    seq: int,
) -> GroundTruthItem:
    """Split the gold_answer into sentences and attach the span as every
    sentence's gold citation list (attribution-first invariant)."""
    answer_sentences = split_sentences(gold_answer)
    if not answer_sentences:
        gold_citations = [list(span.sentence_ids)]
    else:
        gold_citations = [list(span.sentence_ids) for _ in answer_sentences]
    return GroundTruthItem(
        question_id=_question_id(span, seq=seq),
        question=question,
        difficulty=span.difficulty,
        gold_answer=gold_answer,
        gold_citations=gold_citations,
        author_model=author_model,
        source_span_sentence_ids=list(span.sentence_ids),
        document_id=span.document_id,
        page=span.page,
        section_path=list(span.section_path),
    )


def generate_item(
    span: Span,
    *,
    client: ChatCompletionsClient,
    model: str,
    author_model: str,
    seq: int,
    temperature: float = 0.3,
    max_tokens: int = 400,
) -> GroundTruthItem:
    """Call the synth-GT model once on ``span`` and build a ``GroundTruthItem``.

    Raises on parse / validation failure so the caller can record the
    failure and move on.
    """
    section = " > ".join(span.section_path) if span.section_path else "(root)"
    user = USER_TEMPLATE.format(
        difficulty=span.difficulty,
        document_id=span.document_id,
        page=span.page,
        section=section,
        span_text=span.text,
    )
    resp = client.complete(
        model=model,
        messages=[SystemMessage(content=SYSTEM_PROMPT), UserMessage(content=user)],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = (resp.choices[0].message.content or "").strip()
    obj = _parse_model_json(content)
    question, gold_answer = _validate_item_fields(obj)
    return _build_item(
        span=span,
        question=question,
        gold_answer=gold_answer,
        author_model=author_model,
        seq=seq,
    )


def generate_synth_gt(
    spans: Sequence[Span],
    *,
    cfg: AzureConfig | None = None,
    client: ChatCompletionsClient | None = None,
    temperature: float = 0.3,
    max_tokens: int = 400,
    seed: int = 7,
    target_counts: dict[Difficulty, int] | None = None,
    on_progress=None,
) -> SynthGTRun:
    """Run synth-GT over ``spans`` using the synth_gt role from :mod:`sentcite.llm`.

    Enforces the three-distinct-models invariant via ``get_binding`` and
    records rag/synth/judge identities on the returned run so downstream
    audit code can refuse same-family results.
    """
    cfg = cfg or AzureConfig.from_env()
    # get_binding runs assert_three_distinct_models internally.
    synth_binding = get_binding("synth_gt", cfg)
    rag_binding = get_binding("rag", cfg)
    judge_binding = get_binding("judge", cfg)
    client = client or get_client("synth_gt", cfg)
    model = get_model_id("synth_gt", cfg)

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    items: list[GroundTruthItem] = []
    failures: list[SynthGTFailure] = []
    for idx, span in enumerate(spans):
        try:
            item = generate_item(
                span,
                client=client,
                model=model,
                author_model=synth_binding.model_identity,
                seq=idx,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            items.append(item)
        except Exception as exc:  # noqa: BLE001 - we want every error preserved
            failures.append(
                SynthGTFailure(
                    span_chunk_id=span.chunk_id,
                    span_sentence_ids=span.sentence_ids,
                    difficulty=span.difficulty,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
        if on_progress is not None:
            on_progress(idx + 1, len(spans), items, failures)

    finished = datetime.now(timezone.utc)
    return SynthGTRun(
        items=items,
        failures=failures,
        author_model=synth_binding.model_identity,
        rag_model=rag_binding.model_identity,
        judge_model=judge_binding.model_identity,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        seed=seed,
        target_counts={k: int(v) for k, v in (target_counts or {}).items()},
        elapsed_seconds=time.perf_counter() - t0,
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def _default_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ")


def write_synth_gt_run(
    run: SynthGTRun,
    *,
    out_dir: Path | str = "data/ground_truth/synthetic",
    run_id: str | None = None,
) -> dict[str, Path]:
    """Persist a run as items.jsonl + failures.jsonl + manifest.json.

    Layout::

        data/ground_truth/synthetic/<run_id>/
            items.jsonl
            failures.jsonl
            manifest.json
    """
    out_dir = Path(out_dir)
    run_id = run_id or _default_run_id()
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    items_path = run_dir / "items.jsonl"
    with items_path.open("w", encoding="utf-8") as f:
        for it in run.items:
            f.write(it.model_dump_json() + "\n")

    failures_path = run_dir / "failures.jsonl"
    with failures_path.open("w", encoding="utf-8") as f:
        for fail in run.failures:
            f.write(
                json.dumps(
                    {
                        "span_chunk_id": fail.span_chunk_id,
                        "span_sentence_ids": list(fail.span_sentence_ids),
                        "difficulty": fail.difficulty,
                        "error": fail.error,
                    }
                )
                + "\n"
            )

    manifest_path = run_dir / "manifest.json"
    manifest = run.to_manifest()
    manifest["run_id"] = run_id
    manifest["items_path"] = str(items_path)
    manifest["failures_path"] = str(failures_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {"items": items_path, "failures": failures_path, "manifest": manifest_path}


def load_synth_gt_items(path: Path | str) -> list[GroundTruthItem]:
    """Load an items.jsonl file back into GroundTruthItem objects."""
    path = Path(path)
    out: list[GroundTruthItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(GroundTruthItem.model_validate_json(line))
    return out
