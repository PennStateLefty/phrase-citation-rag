"""Self-consistency metric — citation stability under re-sampling.

This is a **GT-free** stability signal. For a fixed question and
retrieval result we run the generator + citation aligner ``N`` times
with a non-zero temperature and measure how much the *set* of cited
source ``sentence_id``s moves.

Headline number we report to the customer deck is ``stability`` — the
all-runs Jaccard (``|∩| / |∪|``) of the cited sentence_id sets. A
pipeline that deserves an auditor's trust should return the *same*
supporting sentences every time it's re-asked the same question; if
different runs land on different sources, that's a hygiene signal the
customer (and we) need to see before scaling.

Design notes:

- Retrieval is called once per question and reused across replicas.
  Retrieval under Entra auth against Azure AI Search is deterministic
  for identical ``(query, query_vector, top_k)``; what we're measuring
  is generator + aligner stability, not search flakiness.
- ``temperature`` defaults to 0.7 (noticeable variation without the
  distribution collapsing to gibberish). Caller can also vary k per run
  via ``k_sentences_per_run`` / ``k_chunks_per_run`` if they want to
  probe retrieval sensitivity explicitly — in that case a fresh
  retrieval is performed for each run and the retrieval stability is
  baked into the same metric.
- Per-answer-sentence alignment across runs is *not* attempted here.
  Answer sentences differ word-for-word across replicas so position-
  based alignment is brittle; the set-level comparison is the robust
  MVP. A future refinement could align sentences by cosine similarity
  of embeddings before computing per-position Jaccard.
- We record the per-sentence-id **frequency** across runs so the eval
  UI can surface "stable anchors" (cited in ≥⌈N/2⌉ runs) vs "drift
  candidates" (cited only once). This is actionable feedback for the
  customer: the stable anchors are the high-confidence citations.

Output contract:

- :class:`ReplicaRun` — one replica of the pipeline.
- :class:`StabilityReport` — all replicas for a single question with
  set-level aggregates and per-sid frequency.
- :class:`StabilityBatch` — many reports (one per question) plus run
  metadata (models, timing).
"""

from __future__ import annotations

import itertools
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, Sequence

from azure.ai.inference import ChatCompletionsClient

from .cite_align import DEFAULT_TAU, DEFAULT_TOPK, cite_answer
from .config import AzureConfig
from .generate import generate
from .llm import get_binding, get_client
from .retrieval import Mode, RetrievalResult, retrieve
from .schema import CitedAnswer

Strategy = Literal["inline_prompted", "post_gen_alignment"]


# ---------------------------------------------------------------------------
# Pure aggregate helpers (no I/O, easy to test)
# ---------------------------------------------------------------------------


def citation_id_set(cited: CitedAnswer) -> set[str]:
    """Flatten every cited ``sentence_id`` in *cited* into one set."""
    ids: set[str] = set()
    for s in cited.sentences:
        for c in s.citations:
            ids.add(c.sentence_id)
    return ids


def intersection_union(sets: Sequence[set[str]]) -> tuple[set[str], set[str]]:
    """Compute ``(intersection, union)`` across a sequence of sets.

    An empty sequence returns two empty sets. For a single set, both
    intersection and union equal that set.
    """
    if not sets:
        return set(), set()
    inter = set(sets[0])
    union: set[str] = set()
    for s in sets:
        inter &= s
        union |= s
    return inter, union


def mean_pairwise_jaccard(sets: Sequence[set[str]]) -> float:
    """Mean Jaccard over all C(N,2) pairs.

    Returns 1.0 for <2 sets (degenerate: no pair disagreements
    possible). Empty-vs-empty pair contributes 1.0 by convention
    (identical absence of citations is perfect agreement).
    """
    if len(sets) < 2:
        return 1.0
    scores: list[float] = []
    for a, b in itertools.combinations(sets, 2):
        if not a and not b:
            scores.append(1.0)
            continue
        if not (a or b):
            scores.append(1.0)
            continue
        inter = len(a & b)
        union = len(a | b)
        scores.append(inter / union if union else 1.0)
    return sum(scores) / len(scores)


def citation_frequency(sets: Sequence[set[str]]) -> dict[str, int]:
    """Count, per sentence_id, how many runs cited it."""
    freq: dict[str, int] = {}
    for s in sets:
        for sid in s:
            freq[sid] = freq.get(sid, 0) + 1
    return freq


def stable_anchor_ids(
    freq: dict[str, int],
    *,
    n_runs: int,
    threshold: float = 0.5,
) -> list[str]:
    """sentence_ids that appear in ≥ ``ceil(threshold * n_runs)`` runs.

    Default ``threshold=0.5`` means "majority of runs". Result is
    sorted by (descending frequency, sentence_id) for deterministic
    output.
    """
    cutoff = max(1, math.ceil(threshold * n_runs))
    return sorted(
        (sid for sid, f in freq.items() if f >= cutoff),
        key=lambda sid: (-freq[sid], sid),
    )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ReplicaRun:
    run_index: int
    temperature: float
    answer_text: str
    citation_ids: list[str]
    per_sentence_citation_ids: list[list[str]]
    n_answer_sentences: int
    latency_ms: float

    @classmethod
    def from_cited(
        cls,
        *,
        run_index: int,
        temperature: float,
        cited: CitedAnswer,
        latency_ms: float,
    ) -> "ReplicaRun":
        per = [[c.sentence_id for c in s.citations] for s in cited.sentences]
        return cls(
            run_index=run_index,
            temperature=temperature,
            answer_text=cited.answer_text,
            citation_ids=sorted(citation_id_set(cited)),
            per_sentence_citation_ids=per,
            n_answer_sentences=len(cited.sentences),
            latency_ms=latency_ms,
        )


@dataclass
class StabilityReport:
    question: str
    strategy: Strategy
    n_runs: int
    temperature: float
    rag_model: str
    retrieval_mode: Mode
    runs: list[ReplicaRun]
    union_ids: list[str]
    intersection_ids: list[str]
    frequency: dict[str, int]
    stable_anchors: list[str]
    stability: float
    mean_pairwise_jaccard: float
    coverage_rate: float
    # Optional — only populated when all runs produced identical answer
    # sentence counts (so per-position comparison is actually meaningful).
    per_sentence_mean_jaccard: list[float] | None = None

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "strategy": self.strategy,
            "n_runs": self.n_runs,
            "temperature": self.temperature,
            "rag_model": self.rag_model,
            "retrieval_mode": self.retrieval_mode,
            "stability": round(self.stability, 4),
            "mean_pairwise_jaccard": round(self.mean_pairwise_jaccard, 4),
            "coverage_rate": round(self.coverage_rate, 4),
            "union_size": len(self.union_ids),
            "intersection_size": len(self.intersection_ids),
            "union_ids": self.union_ids,
            "intersection_ids": self.intersection_ids,
            "frequency": self.frequency,
            "stable_anchors": self.stable_anchors,
            "per_sentence_mean_jaccard": self.per_sentence_mean_jaccard,
            "runs": [
                {
                    "run_index": r.run_index,
                    "temperature": r.temperature,
                    "answer_text": r.answer_text,
                    "citation_ids": r.citation_ids,
                    "per_sentence_citation_ids": r.per_sentence_citation_ids,
                    "n_answer_sentences": r.n_answer_sentences,
                    "latency_ms": round(r.latency_ms, 2),
                }
                for r in self.runs
            ],
        }


@dataclass
class StabilityBatch:
    reports: list[StabilityReport]
    rag_model: str
    retrieval_mode: Mode
    strategy: Strategy
    n_runs: int
    temperature: float
    started_at: str
    finished_at: str
    elapsed_seconds: float

    def to_summary(self) -> dict:
        n = len(self.reports)
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "rag_model": self.rag_model,
            "retrieval_mode": self.retrieval_mode,
            "strategy": self.strategy,
            "n_runs": self.n_runs,
            "temperature": self.temperature,
            "items": n,
            "mean_stability": round(
                sum(r.stability for r in self.reports) / n, 4
            ) if n else 0.0,
            "mean_pairwise_jaccard": round(
                sum(r.mean_pairwise_jaccard for r in self.reports) / n, 4
            ) if n else 0.0,
            "mean_coverage_rate": round(
                sum(r.coverage_rate for r in self.reports) / n, 4
            ) if n else 0.0,
        }


# ---------------------------------------------------------------------------
# Report construction (pure given a list of CitedAnswer — easy to test)
# ---------------------------------------------------------------------------


def build_report_from_replicas(
    *,
    question: str,
    strategy: Strategy,
    temperature: float,
    rag_model: str,
    retrieval_mode: Mode,
    replicas: list[ReplicaRun],
    stable_anchor_threshold: float = 0.5,
) -> StabilityReport:
    sets = [set(r.citation_ids) for r in replicas]
    inter, union = intersection_union(sets)
    stability = (len(inter) / len(union)) if union else 1.0
    freq = citation_frequency(sets)
    anchors = stable_anchor_ids(
        freq, n_runs=len(replicas), threshold=stable_anchor_threshold
    )
    coverage_rate = (
        sum(1 for s in sets if s) / len(sets) if sets else 0.0
    )

    # Per-position comparison only when answer shape matches across all runs.
    per_sentence_mean: list[float] | None = None
    if replicas:
        shape = replicas[0].n_answer_sentences
        if shape > 0 and all(r.n_answer_sentences == shape for r in replicas):
            per_sentence_mean = []
            for i in range(shape):
                per_sets = [
                    set(r.per_sentence_citation_ids[i]) for r in replicas
                ]
                per_sentence_mean.append(mean_pairwise_jaccard(per_sets))

    return StabilityReport(
        question=question,
        strategy=strategy,
        n_runs=len(replicas),
        temperature=temperature,
        rag_model=rag_model,
        retrieval_mode=retrieval_mode,
        runs=replicas,
        union_ids=sorted(union),
        intersection_ids=sorted(inter),
        frequency=dict(sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        stable_anchors=anchors,
        stability=stability,
        mean_pairwise_jaccard=mean_pairwise_jaccard(sets),
        coverage_rate=coverage_rate,
        per_sentence_mean_jaccard=per_sentence_mean,
    )


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


def run_self_consistency(
    question: str,
    *,
    strategy: Strategy,
    n_runs: int = 5,
    temperature: float = 0.7,
    mode: Mode = "dual",
    k_sentences: int = 20,
    k_chunks: int = 5,
    tau: float = DEFAULT_TAU,
    top_k: int = DEFAULT_TOPK,
    retrieval: RetrievalResult | None = None,
    cfg: AzureConfig | None = None,
    client: ChatCompletionsClient | None = None,
    stable_anchor_threshold: float = 0.5,
) -> StabilityReport:
    """Run the generator+aligner ``n_runs`` times and report stability.

    Retrieval is performed once (or taken from *retrieval* if caller
    pre-ran it) and reused across replicas. The RAG generator is
    re-invoked per replica at ``temperature`` so each answer is an
    independent sample from the model.

    Strategy must be specified explicitly (no default) — stability
    numbers are strategy-specific and averaging across strategies
    would be misleading.
    """
    if n_runs < 1:
        raise ValueError("n_runs must be >= 1")
    cfg = cfg or AzureConfig.from_env()
    binding = get_binding("rag", cfg)
    client = client or get_client("rag", cfg)

    result = retrieval or retrieve(
        question, cfg=cfg, mode=mode, k_sentences=k_sentences, k_chunks=k_chunks
    )

    replicas: list[ReplicaRun] = []
    for i in range(n_runs):
        t0 = time.perf_counter()
        gen = generate(
            question,
            result,
            strategy=strategy,
            cfg=cfg,
            client=client,
            temperature=temperature,
        )
        cited = cite_answer(gen, result, cfg=cfg, tau=tau, top_k=top_k)
        dt = (time.perf_counter() - t0) * 1000
        replicas.append(
            ReplicaRun.from_cited(
                run_index=i,
                temperature=temperature,
                cited=cited,
                latency_ms=dt,
            )
        )

    return build_report_from_replicas(
        question=question,
        strategy=strategy,
        temperature=temperature,
        rag_model=binding.model_identity,
        retrieval_mode=result.mode,
        replicas=replicas,
        stable_anchor_threshold=stable_anchor_threshold,
    )


def run_self_consistency_batch(
    questions: Iterable[str],
    *,
    strategy: Strategy,
    n_runs: int = 5,
    temperature: float = 0.7,
    mode: Mode = "dual",
    k_sentences: int = 20,
    k_chunks: int = 5,
    tau: float = DEFAULT_TAU,
    top_k: int = DEFAULT_TOPK,
    cfg: AzureConfig | None = None,
    client: ChatCompletionsClient | None = None,
    on_progress=None,
    stable_anchor_threshold: float = 0.5,
) -> StabilityBatch:
    """Batched self-consistency over many questions."""
    cfg = cfg or AzureConfig.from_env()
    binding = get_binding("rag", cfg)
    client = client or get_client("rag", cfg)

    questions_list = list(questions)
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    reports: list[StabilityReport] = []
    for idx, q in enumerate(questions_list):
        report = run_self_consistency(
            q,
            strategy=strategy,
            n_runs=n_runs,
            temperature=temperature,
            mode=mode,
            k_sentences=k_sentences,
            k_chunks=k_chunks,
            tau=tau,
            top_k=top_k,
            cfg=cfg,
            client=client,
            stable_anchor_threshold=stable_anchor_threshold,
        )
        reports.append(report)
        if on_progress is not None:
            on_progress(idx + 1, len(questions_list), reports)

    finished = datetime.now(timezone.utc)
    return StabilityBatch(
        reports=reports,
        rag_model=binding.model_identity,
        retrieval_mode=mode,
        strategy=strategy,
        n_runs=n_runs,
        temperature=temperature,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        elapsed_seconds=time.perf_counter() - t0,
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def write_stability_batch(
    batch: StabilityBatch,
    *,
    out_dir: Path | str,
    run_id: str | None = None,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    reports_path = run_dir / "stability.jsonl"
    with reports_path.open("w", encoding="utf-8") as f:
        for rep in batch.reports:
            f.write(json.dumps(rep.to_dict()) + "\n")

    manifest_path = run_dir / "manifest.json"
    manifest = batch.to_summary()
    manifest["run_id"] = run_id
    manifest["reports_path"] = str(reports_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {"reports": reports_path, "manifest": manifest_path}
