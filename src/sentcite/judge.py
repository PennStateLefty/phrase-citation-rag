"""LLM-as-judge attribution faithfulness.

For each ``(answer_sentence, citation)`` pair in a :class:`CitedAnswer`,
ask a judge model — the third distinct model in the stack, distinct from
both the RAG generator and the synth-GT author — whether the cited
source sentence actually entails the claim.

This is a **GT-free** metric. It's usable from day one and is the
primary signal we report to the customer until Phase 1b ground truth
exists: "for the pipeline's own citations, how often is each cited
source actually supporting the claim the answer sentence makes?"

Output contract:

- :class:`FaithfulnessJudgment` per (answer_sentence, citation) pair —
  ``entails`` (bool) + ``reason`` (short string).
- :class:`SentenceFaithfulness` aggregates a sentence's judgments:
  ``any_faithful`` (≥1 citation entails the claim) and ``all_faithful``
  (every citation entails it).
- :class:`FaithfulnessReport` rolls everything up: per-sentence summary,
  totals, and the headline ``percent_faithful`` (% of citations that
  entail), plus the stricter ``percent_sentences_any_faithful`` which
  answers "what fraction of answer sentences had at least one valid
  citation?"

All three model identities (RAG, synth-GT, judge) are recorded on the
report so eval output can refuse same-family contamination.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, Sequence

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage

from .config import AzureConfig
from .llm import get_binding, get_client, get_model_id
from .retrieval import RetrievalResult
from .schema import Citation, CitedAnswer, CitedSentence
from .synth_gt import _parse_model_json


# ---------------------------------------------------------------------------
# Source-sentence lookup
# ---------------------------------------------------------------------------


def build_source_text_lookup(result: RetrievalResult) -> dict[str, dict]:
    """Flatten a RetrievalResult to ``{sentence_id: {text, chunk_id, ...}}``.

    Uses nested chunk sentences (richer section_path) first, then layout-Y
    candidate hits as a fallback. This is the universe of sentence_ids a
    CitedAnswer's citations can legitimately reference.
    """
    out: dict[str, dict] = {}
    for chunk in result.chunks:
        for s in chunk.sentences or []:
            sid = s.get("sentence_id")
            if sid and sid not in out:
                out[sid] = s
    for cand in result.sentence_candidates:
        if cand.sentence_id not in out:
            out[cand.sentence_id] = {
                "sentence_id": cand.sentence_id,
                "chunk_id": cand.chunk_id,
                "document_id": cand.document_id,
                "page": cand.page,
                "section_path": cand.section_path,
                "text": cand.text,
            }
    return out


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


JUDGE_SYSTEM = """You grade whether a SOURCE sentence from an IRS \
publication entails a CLAIM from an AI-generated answer.

Return ONLY a JSON array. Each element corresponds to one candidate \
source, in the order given, and has this exact shape:

{"entails": true|false, "reason": "<one-sentence explanation>"}

Rules:
- 'entails' = true iff the SOURCE, read on its own, directly establishes \
the CLAIM. The same rule, the same number, the same definition, or a \
clear restatement that leaves no ambiguity.
- If the SOURCE is only topically related, partially overlapping, \
mentions a related concept, or is weaker/stronger than the claim, \
return false.
- If the CLAIM adds facts (numbers, dates, conditions, actors) that the \
SOURCE does not state, return false.
- Be conservative. The user is a tax auditor deciding whether to sign \
off on this citation; ambiguity means false.
- Output the JSON array only. No prose before or after, no code fences."""


JUDGE_USER = """CLAIM:
{claim}

CANDIDATE SOURCES (evaluate each independently):
{sources}

Return the JSON array now."""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FaithfulnessJudgment:
    answer_sentence_index: int
    answer_sentence_text: str
    citation_sentence_id: str
    citation_chunk_id: str
    citation_source: Literal["llm", "aligner"]
    citation_confidence: float
    entails: bool
    reason: str


@dataclass
class SentenceFaithfulness:
    index: int
    text: str
    judgments: list[FaithfulnessJudgment]

    @property
    def citation_count(self) -> int:
        return len(self.judgments)

    @property
    def faithful_count(self) -> int:
        return sum(1 for j in self.judgments if j.entails)

    @property
    def any_faithful(self) -> bool:
        return any(j.entails for j in self.judgments)

    @property
    def all_faithful(self) -> bool:
        return self.citation_count > 0 and all(j.entails for j in self.judgments)


@dataclass
class FaithfulnessReport:
    question: str
    strategy: Literal["inline_prompted", "post_gen_alignment"]
    rag_model: str
    synth_model: str
    judge_model: str
    sentences: list[SentenceFaithfulness]
    errors: list[str] = field(default_factory=list)

    @property
    def total_citations(self) -> int:
        return sum(s.citation_count for s in self.sentences)

    @property
    def faithful_citations(self) -> int:
        return sum(s.faithful_count for s in self.sentences)

    @property
    def percent_faithful(self) -> float:
        n = self.total_citations
        return (self.faithful_citations / n * 100) if n else 0.0

    @property
    def percent_sentences_any_faithful(self) -> float:
        cited = [s for s in self.sentences if s.citation_count > 0]
        if not cited:
            return 0.0
        return sum(1 for s in cited if s.any_faithful) / len(cited) * 100

    @property
    def coverage(self) -> float:
        """Fraction of answer sentences that received >=1 citation."""
        if not self.sentences:
            return 0.0
        return sum(1 for s in self.sentences if s.citation_count > 0) / len(
            self.sentences
        ) * 100

    def to_summary(self) -> dict:
        return {
            "question": self.question,
            "strategy": self.strategy,
            "rag_model": self.rag_model,
            "synth_model": self.synth_model,
            "judge_model": self.judge_model,
            "total_sentences": len(self.sentences),
            "total_citations": self.total_citations,
            "faithful_citations": self.faithful_citations,
            "percent_faithful": round(self.percent_faithful, 2),
            "percent_sentences_any_faithful": round(
                self.percent_sentences_any_faithful, 2
            ),
            "coverage": round(self.coverage, 2),
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------


def _format_sources(citations: Sequence[Citation], lookup: dict[str, dict]) -> str:
    lines: list[str] = []
    for i, c in enumerate(citations):
        src = lookup.get(c.sentence_id, {})
        section = " > ".join(src.get("section_path") or c.section_path or []) or "(root)"
        text = (src.get("text") or "").strip().replace("\n", " ")
        if not text:
            text = "(source text unavailable — citation references an id not in the retrieval result)"
        lines.append(
            f"[{i}] (doc={c.document_id}, p{c.page}, {section}) {text}"
        )
    return "\n".join(lines)


def _judge_sentence(
    sentence: CitedSentence,
    lookup: dict[str, dict],
    *,
    client: ChatCompletionsClient,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 500,
) -> tuple[list[FaithfulnessJudgment], str | None]:
    """Judge every citation on one answer sentence in a single LLM call.

    Returns ``(judgments, error)``. ``error`` is ``None`` on success; when
    set, ``judgments`` contains conservative defaults (entails=False,
    reason=the error) so the overall report still accounts for each
    citation.
    """
    if not sentence.citations:
        return [], None
    user = JUDGE_USER.format(
        claim=sentence.text,
        sources=_format_sources(sentence.citations, lookup),
    )
    try:
        resp = client.complete(
            model=model,
            messages=[
                SystemMessage(content=JUDGE_SYSTEM),
                UserMessage(content=user),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback_judgments(sentence, reason=f"judge call failed: {type(exc).__name__}: {exc}"), str(exc)

    content = (resp.choices[0].message.content or "").strip()
    try:
        parsed = _parse_judge_array(content, expected=len(sentence.citations))
    except ValueError as exc:
        return _fallback_judgments(sentence, reason=f"parse failed: {exc}"), str(exc)

    return [
        FaithfulnessJudgment(
            answer_sentence_index=sentence.index,
            answer_sentence_text=sentence.text,
            citation_sentence_id=cit.sentence_id,
            citation_chunk_id=cit.chunk_id,
            citation_source=cit.source,
            citation_confidence=cit.confidence,
            entails=bool(parsed[i]["entails"]),
            reason=str(parsed[i].get("reason", ""))[:300],
        )
        for i, cit in enumerate(sentence.citations)
    ], None


def _parse_judge_array(content: str, *, expected: int) -> list[dict]:
    """Parse the judge's JSON array. Accepts objects-wrapping-arrays too."""
    s = content.strip()
    # Strip fenced code blocks.
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:].lstrip()
    # Direct array parse.
    try:
        arr = json.loads(s)
    except json.JSONDecodeError:
        # Fall back to tolerant extraction (scans for {...}) and wrap into list.
        # If the judge returned a single object for one citation we accept it.
        obj = _parse_model_json(content)
        arr = [obj]
    if isinstance(arr, dict):
        # Tolerate {"judgments": [...]} wrapping.
        for key in ("judgments", "results", "items"):
            if key in arr and isinstance(arr[key], list):
                arr = arr[key]
                break
        else:
            arr = [arr]
    if not isinstance(arr, list):
        raise ValueError(f"expected JSON array, got {type(arr).__name__}")
    if len(arr) != expected:
        # Pad with conservative defaults or truncate to match.
        if len(arr) < expected:
            for _ in range(expected - len(arr)):
                arr.append(
                    {
                        "entails": False,
                        "reason": "judge returned fewer entries than citations",
                    }
                )
        else:
            arr = arr[:expected]
    for entry in arr:
        if not isinstance(entry, dict) or "entails" not in entry:
            raise ValueError(f"malformed entry in judge output: {entry!r}")
    return arr


def _fallback_judgments(sentence: CitedSentence, *, reason: str) -> list[FaithfulnessJudgment]:
    return [
        FaithfulnessJudgment(
            answer_sentence_index=sentence.index,
            answer_sentence_text=sentence.text,
            citation_sentence_id=cit.sentence_id,
            citation_chunk_id=cit.chunk_id,
            citation_source=cit.source,
            citation_confidence=cit.confidence,
            entails=False,
            reason=reason[:300],
        )
        for cit in sentence.citations
    ]


def judge_faithfulness(
    cited: CitedAnswer,
    result: RetrievalResult,
    *,
    cfg: AzureConfig | None = None,
    client: ChatCompletionsClient | None = None,
    temperature: float = 0.0,
    max_tokens: int = 500,
) -> FaithfulnessReport:
    """Judge every citation on every answer sentence in ``cited``.

    One LLM call per answer sentence (batched over that sentence's
    citations). Same-family contamination is blocked at the binding
    resolver: :func:`sentcite.llm.get_binding` enforces three distinct
    model identities before any call is made.

    A per-answer-sentence guard also refuses to judge if the recorded
    ``cited.model`` matches the judge model identity — catches the case
    where ``CitedAnswer`` was produced under an earlier, different
    configuration.
    """
    cfg = cfg or AzureConfig.from_env()
    judge_binding = get_binding("judge", cfg)
    rag_binding = get_binding("rag", cfg)
    synth_binding = get_binding("synth_gt", cfg)
    client = client or get_client("judge", cfg)
    model = get_model_id("judge", cfg)

    if cited.model and cited.model.lower() == judge_binding.model_identity.lower():
        raise RuntimeError(
            "contamination guard: the CitedAnswer was produced by "
            f"{cited.model!r} which matches the current judge model "
            f"{judge_binding.model_identity!r}. Reconfigure the judge role."
        )

    lookup = build_source_text_lookup(result)

    sentences: list[SentenceFaithfulness] = []
    errors: list[str] = []
    for s in cited.sentences:
        judgments, err = _judge_sentence(
            s, lookup, client=client, model=model,
            temperature=temperature, max_tokens=max_tokens,
        )
        if err:
            errors.append(f"sentence {s.index}: {err}")
        sentences.append(
            SentenceFaithfulness(index=s.index, text=s.text, judgments=judgments)
        )

    return FaithfulnessReport(
        question=cited.question,
        strategy=cited.strategy,
        rag_model=rag_binding.model_identity,
        synth_model=synth_binding.model_identity,
        judge_model=judge_binding.model_identity,
        sentences=sentences,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Batched judging
# ---------------------------------------------------------------------------


@dataclass
class FaithfulnessBatch:
    reports: list[FaithfulnessReport]
    rag_model: str
    synth_model: str
    judge_model: str
    started_at: str
    finished_at: str
    elapsed_seconds: float

    def to_summary(self) -> dict:
        n = len(self.reports)
        total_cits = sum(r.total_citations for r in self.reports)
        faithful = sum(r.faithful_citations for r in self.reports)
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "rag_model": self.rag_model,
            "synth_model": self.synth_model,
            "judge_model": self.judge_model,
            "items": n,
            "total_citations": total_cits,
            "faithful_citations": faithful,
            "percent_faithful": round((faithful / total_cits * 100) if total_cits else 0.0, 2),
        }


def judge_faithfulness_batch(
    pairs: Iterable[tuple[CitedAnswer, RetrievalResult]],
    *,
    cfg: AzureConfig | None = None,
    client: ChatCompletionsClient | None = None,
    on_progress=None,
) -> FaithfulnessBatch:
    """Judge many (CitedAnswer, RetrievalResult) pairs. Useful for eval loops."""
    cfg = cfg or AzureConfig.from_env()
    judge_binding = get_binding("judge", cfg)
    rag_binding = get_binding("rag", cfg)
    synth_binding = get_binding("synth_gt", cfg)
    client = client or get_client("judge", cfg)

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    reports: list[FaithfulnessReport] = []
    pairs_list = list(pairs)
    for idx, (cited, result) in enumerate(pairs_list):
        reports.append(
            judge_faithfulness(cited, result, cfg=cfg, client=client)
        )
        if on_progress is not None:
            on_progress(idx + 1, len(pairs_list), reports)

    finished = datetime.now(timezone.utc)
    return FaithfulnessBatch(
        reports=reports,
        rag_model=rag_binding.model_identity,
        synth_model=synth_binding.model_identity,
        judge_model=judge_binding.model_identity,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        elapsed_seconds=time.perf_counter() - t0,
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def _report_to_dict(report: FaithfulnessReport) -> dict:
    return {
        **report.to_summary(),
        "sentences": [
            {
                "index": s.index,
                "text": s.text,
                "citation_count": s.citation_count,
                "faithful_count": s.faithful_count,
                "any_faithful": s.any_faithful,
                "all_faithful": s.all_faithful,
                "judgments": [
                    {
                        "citation_sentence_id": j.citation_sentence_id,
                        "citation_chunk_id": j.citation_chunk_id,
                        "citation_source": j.citation_source,
                        "citation_confidence": j.citation_confidence,
                        "entails": j.entails,
                        "reason": j.reason,
                    }
                    for j in s.judgments
                ],
            }
            for s in report.sentences
        ],
    }


def write_faithfulness_batch(
    batch: FaithfulnessBatch,
    *,
    out_dir: Path | str,
    run_id: str | None = None,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    reports_path = run_dir / "faithfulness.jsonl"
    with reports_path.open("w", encoding="utf-8") as f:
        for rep in batch.reports:
            f.write(json.dumps(_report_to_dict(rep)) + "\n")

    manifest_path = run_dir / "manifest.json"
    manifest = batch.to_summary()
    manifest["run_id"] = run_id
    manifest["reports_path"] = str(reports_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {"reports": reports_path, "manifest": manifest_path}
