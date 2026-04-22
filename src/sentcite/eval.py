"""Phase 1a evaluation harness.

One entry point — :func:`evaluate_gt_set` — takes a list of curated
:class:`~sentcite.schema.GroundTruthItem` objects and produces an
:class:`EvalReport` with per-strategy P/R/F1, coverage, retrieval
recall@k, and optional LLM-judge faithfulness + self-consistency
stability. The report knows how to emit a side-by-side Strategy A vs
Strategy B markdown table for the customer deck.

Design notes:

- **Citation comparison is set-based at the question level.** The
  gold ``gold_citations`` schema is one set per *gold* answer sentence,
  but the predicted answer may have a different sentence count / order
  than the gold answer — any per-position alignment between predicted
  and gold is brittle and would silently hide signal. We flatten both
  sides to a single set and score one P/R/F per question. Coverage is
  reported separately (fraction of predicted answer sentences that
  received any citation) so readers can see that alongside F1.

- **Union-labeler additions are already merged** into every per-answer-
  sentence list in ``gold_citations`` by :mod:`sentcite.quality_gates`,
  so flattening picks them up automatically. We don't re-merge here.

- **Retrieval recall@k** counts a gold sid as covered if it appears in
  the Layout-Y candidate pool *or* inside a Layout-X chunk's nested
  sentences (both are reachable for citation). This is the honest
  ceiling on what the aligner/prompter can cite.

- **Per-difficulty aggregation** is offered because the curated 67-
  item set skews easy→medium; headline F1 alone hides that hard-tier
  cases may underperform. Every roll-up is available by difficulty.

- **Judge and self-consistency are optional** — expensive calls. When
  enabled, they run on the same items and stitch into the same
  :class:`EvalReport`.

Output contract:

- :class:`ItemEval` — per-question, per-strategy raw + metrics.
- :class:`StrategyEvalSummary` — macro aggregates for one strategy.
- :class:`EvalReport` — both strategies + models + optional
  faithfulness/stability summaries. ``to_markdown_table()`` for the
  customer deck.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, Sequence

from azure.ai.inference import ChatCompletionsClient

from .cite_align import DEFAULT_TAU, DEFAULT_TOPK, cite_answer
from .config import AzureConfig
from .generate import generate
from .judge import FaithfulnessReport, judge_faithfulness
from .layperson_review import LaypersonReview, summarize_reviews
from .llm import get_binding, get_client
from .retrieval import Mode, RetrievalResult, retrieve
from .schema import CitedAnswer, GroundTruthItem
from .self_consistency import StabilityReport, run_self_consistency

Strategy = Literal["inline_prompted", "post_gen_alignment"]
Difficulty = Literal["easy", "medium", "hard"]


# ---------------------------------------------------------------------------
# Pure metric helpers
# ---------------------------------------------------------------------------


def flatten_gold_ids(gt: GroundTruthItem) -> set[str]:
    """Every supporting sentence_id across every gold answer sentence."""
    ids: set[str] = set()
    for bucket in gt.gold_citations:
        ids.update(bucket)
    return ids


def flatten_pred_ids(cited: CitedAnswer) -> set[str]:
    ids: set[str] = set()
    for s in cited.sentences:
        for c in s.citations:
            ids.add(c.sentence_id)
    return ids


def retrieval_sid_pool(result: RetrievalResult) -> set[str]:
    """All cite-able sids reachable from a retrieval result.

    Layout-Y candidates plus every nested sentence in Layout-X chunks.
    These are the sids a strategy could possibly cite.
    """
    pool: set[str] = set()
    for s in result.sentence_candidates:
        pool.add(s.sentence_id)
    for c in result.chunks:
        for s in c.sentences:
            sid = s.get("sentence_id")
            if sid:
                pool.add(sid)
    return pool


def prf(predicted: set[str], gold: set[str]) -> tuple[float, float, float]:
    """Precision / Recall / F1 for set-level comparison.

    No-citation-no-gold is treated as *vacuously correct* (1.0) — the
    harness upstream should only feed items that actually have gold
    citations, so this is defensive. No-cite-but-gold is 0; cite-but-
    no-gold is 0 (treats the citation as spurious).
    """
    if not predicted and not gold:
        return 1.0, 1.0, 1.0
    if not predicted or not gold:
        return 0.0, 0.0, 0.0
    tp = len(predicted & gold)
    p = tp / len(predicted)
    r = tp / len(gold)
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def coverage(cited: CitedAnswer) -> float:
    """Fraction of answer sentences that received at least one citation."""
    if not cited.sentences:
        return 0.0
    cited_count = sum(1 for s in cited.sentences if s.citations)
    return cited_count / len(cited.sentences)


def retrieval_recall(gold: set[str], result: RetrievalResult) -> float:
    """Fraction of gold sids that are reachable in the retrieval result.

    The ceiling on recall the citation stage can possibly achieve.
    """
    if not gold:
        return 1.0
    pool = retrieval_sid_pool(result)
    return len(gold & pool) / len(gold)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ItemEval:
    question_id: str
    question: str
    difficulty: Difficulty
    strategy: Strategy
    precision: float
    recall: float
    f1: float
    coverage: float
    retrieval_recall_at_k: float
    n_answer_sentences: int
    n_gold_ids: int
    n_pred_ids: int
    # Attached artifacts (kept in-memory for downstream enrichment,
    # stripped before serialization).
    cited: CitedAnswer | None = None
    retrieval: RetrievalResult | None = None
    latency_ms: float = 0.0
    # Optional enrichments (populated by enrich_* helpers).
    faithfulness: FaithfulnessReport | None = None
    stability: StabilityReport | None = None
    # Error bookkeeping for batch resilience: if generation / citation
    # raised (content filter, transient API error, etc.) the item is
    # recorded with zero scores and this field non-empty so roll-ups
    # can separate signal from platform-noise.
    error: str | None = None
    # Layperson review metadata (non-SME). Surfaced in aggregates and
    # markdown so readers don't conflate it with domain validation.
    reviewer_confidence: Literal["high", "medium", "low"] | None = None
    reviewer_role: str | None = None
    reviewer_flags: tuple[str, ...] = ()
    reviewer_notes: str = ""

    def to_dict(self) -> dict:
        d = {
            "question_id": self.question_id,
            "question": self.question,
            "difficulty": self.difficulty,
            "strategy": self.strategy,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "coverage": round(self.coverage, 4),
            "retrieval_recall_at_k": round(self.retrieval_recall_at_k, 4),
            "n_answer_sentences": self.n_answer_sentences,
            "n_gold_ids": self.n_gold_ids,
            "n_pred_ids": self.n_pred_ids,
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.cited is not None:
            d["answer_text"] = self.cited.answer_text
            d["pred_citation_ids"] = sorted(flatten_pred_ids(self.cited))
        if self.faithfulness is not None:
            d["percent_faithful"] = round(self.faithfulness.percent_faithful, 2)
            d["percent_sentences_any_faithful"] = round(
                self.faithfulness.percent_sentences_any_faithful, 2
            )
        if self.stability is not None:
            d["stability"] = round(self.stability.stability, 4)
            d["mean_pairwise_jaccard"] = round(
                self.stability.mean_pairwise_jaccard, 4
            )
        if self.error is not None:
            d["error"] = self.error
        if self.reviewer_confidence is not None:
            d["reviewer_confidence"] = self.reviewer_confidence
            d["reviewer_role"] = self.reviewer_role
            d["reviewer_flags"] = list(self.reviewer_flags)
            d["reviewer_notes"] = self.reviewer_notes
        return d


@dataclass
class StrategyEvalSummary:
    strategy: Strategy
    items: list[ItemEval]
    # Macro means across items.
    macro_precision: float
    macro_recall: float
    macro_f1: float
    macro_coverage: float
    macro_retrieval_recall_at_k: float
    # Per-difficulty macro F1 (None for empty slices).
    by_difficulty: dict[Difficulty, dict[str, float]]
    # Optional enrichments.
    macro_percent_faithful: float | None = None
    macro_stability: float | None = None
    # Non-SME reviewer buckets. Maps confidence → {"n","f1","precision",
    # "recall","coverage"}. Only populated when reviews are stitched in.
    by_reviewer_confidence: dict[str, dict[str, float]] = field(
        default_factory=dict
    )

    def to_summary(self) -> dict:
        return {
            "strategy": self.strategy,
            "n_items": len(self.items),
            "macro_precision": round(self.macro_precision, 4),
            "macro_recall": round(self.macro_recall, 4),
            "macro_f1": round(self.macro_f1, 4),
            "macro_coverage": round(self.macro_coverage, 4),
            "macro_retrieval_recall_at_k": round(
                self.macro_retrieval_recall_at_k, 4
            ),
            "by_difficulty": {
                k: {kk: round(vv, 4) for kk, vv in v.items()}
                for k, v in self.by_difficulty.items()
            },
            "macro_percent_faithful": (
                round(self.macro_percent_faithful, 2)
                if self.macro_percent_faithful is not None
                else None
            ),
            "macro_stability": (
                round(self.macro_stability, 4)
                if self.macro_stability is not None
                else None
            ),
            "by_reviewer_confidence": {
                k: {kk: round(vv, 4) for kk, vv in v.items()}
                for k, v in self.by_reviewer_confidence.items()
            },
        }


@dataclass
class EvalReport:
    rag_model: str
    synth_model: str
    judge_model: str
    retrieval_mode: Mode
    k_sentences: int
    k_chunks: int
    tau: float
    top_k: int
    strategies: dict[Strategy, StrategyEvalSummary]
    started_at: str
    finished_at: str
    elapsed_seconds: float
    # Optional: layperson review coverage summary (counts by confidence,
    # top flags). Populated when reviews are passed to evaluate_gt_set.
    reviews_summary: dict | None = None

    def to_summary(self) -> dict:
        return {
            "rag_model": self.rag_model,
            "synth_model": self.synth_model,
            "judge_model": self.judge_model,
            "retrieval_mode": self.retrieval_mode,
            "k_sentences": self.k_sentences,
            "k_chunks": self.k_chunks,
            "tau": self.tau,
            "top_k": self.top_k,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "strategies": {
                k: v.to_summary() for k, v in self.strategies.items()
            },
            "reviews_summary": self.reviews_summary,
        }

    def to_markdown_table(self) -> str:
        """Side-by-side comparison table for the customer deck."""
        rows = []
        strategies = list(self.strategies.keys())
        header = ["Metric"] + strategies
        rows.append("| " + " | ".join(header) + " |")
        rows.append("| " + " | ".join(["---"] * len(header)) + " |")

        def row(label: str, getter) -> list[str]:
            cells = [label]
            for s in strategies:
                v = getter(self.strategies[s])
                cells.append("n/a" if v is None else f"{v:.3f}")
            return cells

        rows.append("| " + " | ".join(row("Precision", lambda s: s.macro_precision)) + " |")
        rows.append("| " + " | ".join(row("Recall", lambda s: s.macro_recall)) + " |")
        rows.append("| " + " | ".join(row("F1", lambda s: s.macro_f1)) + " |")
        rows.append("| " + " | ".join(row("Coverage", lambda s: s.macro_coverage)) + " |")
        rows.append(
            "| " + " | ".join(row("Retrieval R@k", lambda s: s.macro_retrieval_recall_at_k)) + " |"
        )
        rows.append(
            "| " + " | ".join(row("Faithful %", lambda s: s.macro_percent_faithful)) + " |"
        )
        rows.append(
            "| " + " | ".join(row("Stability", lambda s: s.macro_stability)) + " |"
        )

        # Per-difficulty F1
        rows.append("")
        rows.append("### F1 by difficulty")
        rows.append("")
        hdr = ["Difficulty"] + strategies
        rows.append("| " + " | ".join(hdr) + " |")
        rows.append("| " + " | ".join(["---"] * len(hdr)) + " |")
        for diff in ("easy", "medium", "hard"):
            cells = [diff]
            for s in strategies:
                bd = self.strategies[s].by_difficulty.get(diff)
                cells.append(f"{bd['f1']:.3f} (n={int(bd['n'])})" if bd else "n/a")
            rows.append("| " + " | ".join(cells) + " |")

        # Reviewer-confidence slice (non-SME). Only render when at least
        # one strategy has any reviewer-tagged items, so unreviewed runs
        # don't clutter the report.
        any_reviewed = any(
            self.strategies[s].by_reviewer_confidence for s in strategies
        )
        if any_reviewed:
            rows.append("")
            rows.append("### F1 by reviewer confidence (non-SME)")
            rows.append("")
            rows.append(
                "_Layperson (ML Eng / PM) spot-check only. Not a "
                "substitute for SME validation._"
            )
            rows.append("")
            hdr = ["Confidence"] + strategies
            rows.append("| " + " | ".join(hdr) + " |")
            rows.append("| " + " | ".join(["---"] * len(hdr)) + " |")
            for conf in ("high", "medium", "low"):
                cells = [conf]
                for s in strategies:
                    br = self.strategies[s].by_reviewer_confidence.get(conf)
                    cells.append(
                        f"{br['f1']:.3f} (n={int(br['n'])})" if br else "n/a"
                    )
                rows.append("| " + " | ".join(cells) + " |")
            if self.reviews_summary:
                total = self.reviews_summary.get("total", 0)
                flags = self.reviews_summary.get("flag_counts", {})
                rows.append("")
                rows.append(f"Reviewed items: **{total}**")
                if flags:
                    rows.append("")
                    rows.append("Top reviewer flags:")
                    for name, count in list(flags.items())[:5]:
                        rows.append(f"- `{name}`: {count}")

        return "\n".join(rows)


# ---------------------------------------------------------------------------
# Scoring primitive (no I/O, easy to test)
# ---------------------------------------------------------------------------


def score_item(
    gt: GroundTruthItem,
    cited: CitedAnswer,
    result: RetrievalResult,
    *,
    strategy: Strategy,
    latency_ms: float = 0.0,
) -> ItemEval:
    gold = flatten_gold_ids(gt)
    pred = flatten_pred_ids(cited)
    p, r, f = prf(pred, gold)
    return ItemEval(
        question_id=gt.question_id,
        question=gt.question,
        difficulty=gt.difficulty,
        strategy=strategy,
        precision=p,
        recall=r,
        f1=f,
        coverage=coverage(cited),
        retrieval_recall_at_k=retrieval_recall(gold, result),
        n_answer_sentences=len(cited.sentences),
        n_gold_ids=len(gold),
        n_pred_ids=len(pred),
        cited=cited,
        retrieval=result,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Aggregation (pure)
# ---------------------------------------------------------------------------


def _mean(values: Iterable[float]) -> float:
    vs = list(values)
    return sum(vs) / len(vs) if vs else 0.0


def summarize_strategy(
    items: list[ItemEval], strategy: Strategy
) -> StrategyEvalSummary:
    by_diff: dict[Difficulty, list[ItemEval]] = defaultdict(list)
    for it in items:
        by_diff[it.difficulty].append(it)

    by_difficulty: dict[Difficulty, dict[str, float]] = {}
    for diff, bucket in by_diff.items():
        by_difficulty[diff] = {
            "n": float(len(bucket)),
            "precision": _mean(i.precision for i in bucket),
            "recall": _mean(i.recall for i in bucket),
            "f1": _mean(i.f1 for i in bucket),
            "coverage": _mean(i.coverage for i in bucket),
            "retrieval_recall_at_k": _mean(
                i.retrieval_recall_at_k for i in bucket
            ),
        }

    faith_vals = [i.faithfulness.percent_faithful for i in items if i.faithfulness]
    stab_vals = [i.stability.stability for i in items if i.stability]

    # Non-SME reviewer buckets.
    by_reviewer: dict[str, list[ItemEval]] = defaultdict(list)
    for it in items:
        if it.reviewer_confidence is not None:
            by_reviewer[it.reviewer_confidence].append(it)
    by_reviewer_summary: dict[str, dict[str, float]] = {}
    for conf, bucket in by_reviewer.items():
        by_reviewer_summary[conf] = {
            "n": float(len(bucket)),
            "precision": _mean(i.precision for i in bucket),
            "recall": _mean(i.recall for i in bucket),
            "f1": _mean(i.f1 for i in bucket),
            "coverage": _mean(i.coverage for i in bucket),
        }

    return StrategyEvalSummary(
        strategy=strategy,
        items=items,
        macro_precision=_mean(i.precision for i in items),
        macro_recall=_mean(i.recall for i in items),
        macro_f1=_mean(i.f1 for i in items),
        macro_coverage=_mean(i.coverage for i in items),
        macro_retrieval_recall_at_k=_mean(i.retrieval_recall_at_k for i in items),
        by_difficulty=by_difficulty,
        macro_percent_faithful=(_mean(faith_vals) if faith_vals else None),
        macro_stability=(_mean(stab_vals) if stab_vals else None),
        by_reviewer_confidence=by_reviewer_summary,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def evaluate_gt_set(
    gt_items: Sequence[GroundTruthItem],
    *,
    strategies: Sequence[Strategy] = ("inline_prompted", "post_gen_alignment"),
    retrieval_mode: Mode = "dual",
    k_sentences: int = 20,
    k_chunks: int = 5,
    tau: float = DEFAULT_TAU,
    top_k: int = DEFAULT_TOPK,
    include_faithfulness: bool = False,
    include_self_consistency: bool = False,
    consistency_runs: int = 5,
    consistency_temperature: float = 0.7,
    cfg: AzureConfig | None = None,
    client: ChatCompletionsClient | None = None,
    on_progress=None,
    reviews: dict[str, LaypersonReview] | None = None,
) -> EvalReport:
    """Run every item under every strategy and aggregate.

    Retrieval is performed once per item (shared across strategies —
    the candidate pool doesn't depend on which strategy reads it).
    Optional enrichments (judge faithfulness, self-consistency) run
    per-item per-strategy after the base scoring pass, so enabling
    them roughly doubles wall-clock.
    """
    cfg = cfg or AzureConfig.from_env()
    rag = get_binding("rag", cfg)
    synth = get_binding("synth_gt", cfg)
    judge_b = get_binding("judge", cfg)
    rag_client = client or get_client("rag", cfg)

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    items_per_strategy: dict[Strategy, list[ItemEval]] = {s: [] for s in strategies}

    for idx, gt in enumerate(gt_items):
        try:
            result = retrieve(
                gt.question,
                cfg=cfg,
                mode=retrieval_mode,
                k_sentences=k_sentences,
                k_chunks=k_chunks,
            )
        except Exception as exc:  # noqa: BLE001 - batch resilience
            err = f"retrieve_failed: {type(exc).__name__}: {exc}"
            gold = flatten_gold_ids(gt)
            for strat in strategies:
                items_per_strategy[strat].append(
                    ItemEval(
                        question_id=gt.question_id, question=gt.question,
                        difficulty=gt.difficulty, strategy=strat,
                        precision=0.0, recall=0.0, f1=0.0, coverage=0.0,
                        retrieval_recall_at_k=0.0,
                        n_answer_sentences=0,
                        n_gold_ids=len(gold), n_pred_ids=0,
                        error=err,
                    )
                )
            if on_progress is not None:
                on_progress(idx + 1, len(gt_items), items_per_strategy)
            continue

        for strat in strategies:
            t_start = time.perf_counter()
            try:
                gen = generate(
                    gt.question, result, strategy=strat, cfg=cfg,
                    client=rag_client, temperature=0.0,
                )
                cited = cite_answer(gen, result, cfg=cfg, tau=tau, top_k=top_k)
                dt = (time.perf_counter() - t_start) * 1000
                it = score_item(
                    gt, cited, result, strategy=strat, latency_ms=dt
                )

                if include_faithfulness:
                    try:
                        it.faithfulness = judge_faithfulness(
                            cited, result, cfg=cfg
                        )
                    except Exception as exc:  # noqa: BLE001
                        it.error = (
                            f"judge_failed: {type(exc).__name__}: {exc}"
                        )
                if include_self_consistency:
                    try:
                        it.stability = run_self_consistency(
                            gt.question, strategy=strat,
                            n_runs=consistency_runs,
                            temperature=consistency_temperature,
                            retrieval=result, cfg=cfg, client=rag_client,
                        )
                    except Exception as exc:  # noqa: BLE001
                        prior = it.error + "; " if it.error else ""
                        it.error = (
                            prior
                            + f"stability_failed: {type(exc).__name__}: {exc}"
                        )

                items_per_strategy[strat].append(it)
            except Exception as exc:  # noqa: BLE001 - batch resilience
                err = f"generate_or_cite_failed: {type(exc).__name__}: {exc}"
                gold = flatten_gold_ids(gt)
                items_per_strategy[strat].append(
                    ItemEval(
                        question_id=gt.question_id, question=gt.question,
                        difficulty=gt.difficulty, strategy=strat,
                        precision=0.0, recall=0.0, f1=0.0, coverage=0.0,
                        retrieval_recall_at_k=retrieval_recall(gold, result),
                        n_answer_sentences=0,
                        n_gold_ids=len(gold), n_pred_ids=0,
                        retrieval=result, error=err,
                    )
                )

        if on_progress is not None:
            on_progress(idx + 1, len(gt_items), items_per_strategy)

    # Stamp reviewer metadata onto each ItemEval so summaries can slice
    # by reviewer_confidence. Non-destructive — items without a matching
    # review stay unchanged.
    if reviews:
        for strat in strategies:
            for it in items_per_strategy[strat]:
                rev = reviews.get(it.question_id)
                if rev is None:
                    continue
                it.reviewer_confidence = rev.confidence
                it.reviewer_role = rev.reviewer_role
                it.reviewer_flags = tuple(rev.flags)
                it.reviewer_notes = rev.notes

    summaries: dict[Strategy, StrategyEvalSummary] = {
        s: summarize_strategy(items_per_strategy[s], s) for s in strategies
    }

    finished = datetime.now(timezone.utc)
    return EvalReport(
        rag_model=rag.model_identity,
        synth_model=synth.model_identity,
        judge_model=judge_b.model_identity,
        retrieval_mode=retrieval_mode,
        k_sentences=k_sentences,
        k_chunks=k_chunks,
        tau=tau,
        top_k=top_k,
        strategies=summaries,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        elapsed_seconds=time.perf_counter() - t0,
        reviews_summary=(summarize_reviews(reviews) if reviews else None),
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def write_eval_report(
    report: EvalReport,
    *,
    out_dir: Path | str,
    run_id: str | None = None,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    items_path = run_dir / "items.jsonl"
    with items_path.open("w", encoding="utf-8") as f:
        for strat, summary in report.strategies.items():
            for it in summary.items:
                f.write(json.dumps(it.to_dict()) + "\n")

    manifest_path = run_dir / "manifest.json"
    manifest = report.to_summary()
    manifest["run_id"] = run_id
    manifest["items_path"] = str(items_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary_path = run_dir / "summary.md"
    md = [
        f"# Phase 1a evaluation — {run_id}",
        "",
        f"- RAG: `{report.rag_model}`",
        f"- Synth-GT: `{report.synth_model}`",
        f"- Judge: `{report.judge_model}`",
        f"- Retrieval: mode=`{report.retrieval_mode}`, "
        f"k_sentences={report.k_sentences}, k_chunks={report.k_chunks}, "
        f"tau={report.tau}, top_k={report.top_k}",
        f"- Elapsed: {report.elapsed_seconds:.1f}s",
        "",
        "## Strategy comparison",
        "",
        report.to_markdown_table(),
        "",
    ]
    summary_path.write_text("\n".join(md), encoding="utf-8")

    return {
        "items": items_path,
        "manifest": manifest_path,
        "summary": summary_path,
    }
