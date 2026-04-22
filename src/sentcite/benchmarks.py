"""Public sentence-attribution benchmark adapter (HAGRID / ALCE).

Runs the sentence-citation pipeline against a human-validated public
benchmark so the customer deck has a second F1 column independent of
our synth-GT loop. This is the credibility check that shows reviewers
the numbers aren't an artifact of our attribution-first synth data.

Design
------

1. A :class:`BenchmarkItem` carries the query, a list of candidate
   :class:`Passage`\\s (the benchmark packages these with the query —
   no Azure Search roundtrip), and a flat set of ``gold_passage_ids``
   that *should* be cited.
2. :func:`build_retrieval_result` synthesizes a
   :class:`~sentcite.retrieval.RetrievalResult` in the shape the rest
   of the pipeline expects: passages become ``ChunkHit``\\s, sentences
   (split with the project's spaCy singleton) become
   ``SentenceHit``\\s. No Azure dependency.
3. :func:`evaluate_benchmark_item` runs ``generate`` + ``cite_answer``
   just like the synth-GT harness, then **derives predicted passage
   ids from the citation chunk_ids** (passage is the coarser grain
   the benchmark scores at). P/R/F1 is computed at the passage level.
4. :func:`evaluate_benchmark` batches it, reusing the existing
   :class:`~sentcite.eval.EvalReport` type so the output plugs into
   the same summary/markdown path.

Loaders
-------

Two lightweight JSONL loaders are included — both accept the raw
dataset files the benchmark authors publish:

- :func:`load_hagrid_jsonl` — HAGRID (Kamalloo et al., 2023). Each
  line: ``{query, quotes: [{idx, text}], answers: [{answer,
  informative, attributable, ...}], ...}``. Gold passages are the
  ``quotes`` that the human annotator marked attributable.
- :func:`load_alce_jsonl` — ALCE ASQA / ELI5. Each line carries a
  ``docs`` list with per-passage text and an ``answer`` with
  ``citations`` pointing at doc indices.

Both loaders tolerate shape drift — unknown keys are ignored, missing
keys fall back to conservative defaults, and entries without any
passages or gold attribution are skipped (can't score them).

IDs are namespaced so nothing collides with the real IRS corpus:

    chunk_id    = "bench::{query_id}::p{passage_idx:04d}"
    sentence_id = "bench::{query_id}::p{passage_idx:04d}::s{sent_idx:03d}"

The ``passage_id`` a caller provides is kept verbatim in the
``SentenceHit.document_id`` slot — downstream scoring extracts
passage_id back out of the chunk_id so gold lookups are exact.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Literal, Sequence

from azure.ai.inference import ChatCompletionsClient

from .chunking import split_sentences
from .cite_align import DEFAULT_TAU, DEFAULT_TOPK, cite_answer
from .config import AzureConfig
from .eval import (
    EvalReport,
    ItemEval,
    StrategyEvalSummary,
    coverage,
    flatten_pred_ids,
    prf,
    summarize_strategy,
)
from .generate import generate
from .llm import get_binding, get_client
from .retrieval import ChunkHit, RetrievalResult, SentenceHit
from .schema import CitedAnswer

Strategy = Literal["inline_prompted", "post_gen_alignment"]
Difficulty = Literal["easy", "medium", "hard"]

_CHUNK_PREFIX = "bench"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Passage:
    passage_id: str
    text: str
    title: str | None = None


@dataclass(frozen=True)
class BenchmarkItem:
    query_id: str
    query: str
    passages: tuple[Passage, ...]
    gold_passage_ids: frozenset[str]
    difficulty: Difficulty = "medium"
    gold_answer: str | None = None
    source: str = "unknown"

    def passage_lookup(self) -> dict[str, Passage]:
        return {p.passage_id: p for p in self.passages}


# ---------------------------------------------------------------------------
# Retrieval synthesis (no Azure)
# ---------------------------------------------------------------------------


def _chunk_id(query_id: str, passage_idx: int) -> str:
    return f"{_CHUNK_PREFIX}::{query_id}::p{passage_idx:04d}"


def _sentence_id(query_id: str, passage_idx: int, sent_idx: int) -> str:
    return f"{_CHUNK_PREFIX}::{query_id}::p{passage_idx:04d}::s{sent_idx:03d}"


def parse_passage_id_from_chunk(chunk_id: str) -> str | None:
    """Recover the *caller-provided* ``passage_id`` stored alongside a chunk.

    The inverse mapping lives in the chunk dict (``document_id``); this
    helper is a fallback when all you have is the chunk_id string —
    returns the synthetic passage prefix ``pNNNN``. Callers that need
    the *original* passage_id must consult a retrieval result directly.
    """
    if not chunk_id.startswith(f"{_CHUNK_PREFIX}::"):
        return None
    parts = chunk_id.split("::")
    if len(parts) < 3:
        return None
    return parts[2]  # "pNNNN"


def build_retrieval_result(item: BenchmarkItem) -> RetrievalResult:
    """Turn a :class:`BenchmarkItem` into a :class:`RetrievalResult`.

    Every passage is emitted as both a :class:`ChunkHit` (so the
    generator can read the full passage as context) and a series of
    :class:`SentenceHit`\\s (so the aligner + inline prompter have a
    sentence-grain citation pool). The caller's original ``passage_id``
    is preserved in the chunk/sentence ``document_id`` field so scoring
    can compare pred vs gold passage ids exactly.
    """
    chunks: list[ChunkHit] = []
    sentences: list[SentenceHit] = []
    section = ["benchmark"]

    for p_idx, passage in enumerate(item.passages):
        c_id = _chunk_id(item.query_id, p_idx)
        spans = split_sentences(passage.text)
        if not spans:
            # Whole passage as one sentence — guarantees >=1 citation target.
            spans = [(0, len(passage.text), passage.text)]

        nested: list[dict] = []
        for s_idx, (start, end, stext) in enumerate(spans):
            sid = _sentence_id(item.query_id, p_idx, s_idx)
            nested.append(
                {
                    "sentence_id": sid,
                    "text": stext,
                    "chunk_id": c_id,
                    "document_id": passage.passage_id,
                    "page": 1,
                    "section_path": section,
                    "char_start": start,
                    "char_end": end,
                }
            )
            sentences.append(
                SentenceHit(
                    sentence_id=sid,
                    chunk_id=c_id,
                    document_id=passage.passage_id,
                    page=1,
                    section_path=section,
                    text=stext,
                )
            )

        chunks.append(
            ChunkHit(
                chunk_id=c_id,
                document_id=passage.passage_id,
                page=1,
                section_path=section,
                text=passage.text,
                token_count=max(1, len(passage.text.split())),
                sentences=nested,
                source="chunk_search",
            )
        )

    return RetrievalResult(
        query=item.query,
        mode="dual",
        chunks=chunks,
        sentence_candidates=sentences,
        chunk_search_hits=len(chunks),
        sentence_search_hits=len(sentences),
    )


# ---------------------------------------------------------------------------
# Passage-level scoring
# ---------------------------------------------------------------------------


def predicted_passage_ids(
    cited: CitedAnswer, retrieval: RetrievalResult
) -> set[str]:
    """Map citation sids to the *original* benchmark ``passage_id``\\s.

    Each sid came from a SentenceHit whose ``document_id`` is the
    caller-supplied passage_id. Lookup is O(1) against a per-retrieval
    dict; returns the set of distinct passage ids the answer cited.
    """
    sid_to_doc = {s.sentence_id: s.document_id for s in retrieval.sentence_candidates}
    for c in retrieval.chunks:
        for s in c.sentences:
            sid_to_doc.setdefault(s["sentence_id"], s["document_id"])
    ids: set[str] = set()
    for s in cited.sentences:
        for c in s.citations:
            pid = sid_to_doc.get(c.sentence_id)
            if pid is not None:
                ids.add(pid)
    return ids


def score_benchmark_item(
    item: BenchmarkItem,
    cited: CitedAnswer,
    retrieval: RetrievalResult,
    *,
    strategy: Strategy,
    latency_ms: float = 0.0,
) -> ItemEval:
    gold = set(item.gold_passage_ids)
    pred = predicted_passage_ids(cited, retrieval)
    p, r, f = prf(pred, gold)
    # Retrieval recall@k is vacuously 1.0 here: the benchmark hands us
    # every passage the answer could cite, so the "retrieval" stage
    # can't miss any gold — this column is retained in the output so
    # the shape matches the synth-GT harness for side-by-side tables.
    return ItemEval(
        question_id=item.query_id,
        question=item.query,
        difficulty=item.difficulty,
        strategy=strategy,
        precision=p,
        recall=r,
        f1=f,
        coverage=coverage(cited),
        retrieval_recall_at_k=1.0,
        n_answer_sentences=len(cited.sentences),
        n_gold_ids=len(gold),
        n_pred_ids=len(pred),
        cited=cited,
        retrieval=retrieval,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def evaluate_benchmark(
    items: Sequence[BenchmarkItem],
    *,
    strategies: Sequence[Strategy] = ("inline_prompted", "post_gen_alignment"),
    tau: float = DEFAULT_TAU,
    top_k: int = DEFAULT_TOPK,
    cfg: AzureConfig | None = None,
    client: ChatCompletionsClient | None = None,
    on_progress=None,
) -> EvalReport:
    """Run the pipeline on public-benchmark items and produce an EvalReport.

    Same error-resilience contract as :func:`sentcite.eval.evaluate_gt_set`
    — a single failed item (content filter, transient API error) is
    recorded with ``error`` set and the batch continues.
    """
    cfg = cfg or AzureConfig.from_env()
    rag = get_binding("rag", cfg)
    synth = get_binding("synth_gt", cfg)
    judge_b = get_binding("judge", cfg)
    rag_client = client or get_client("rag", cfg)

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    buckets: dict[Strategy, list[ItemEval]] = {s: [] for s in strategies}

    for idx, item in enumerate(items):
        retrieval = build_retrieval_result(item)
        for strat in strategies:
            t_start = time.perf_counter()
            try:
                gen = generate(
                    item.query, retrieval, strategy=strat, cfg=cfg,
                    client=rag_client, temperature=0.0,
                )
                cited = cite_answer(
                    gen, retrieval, cfg=cfg, tau=tau, top_k=top_k
                )
                dt = (time.perf_counter() - t_start) * 1000
                buckets[strat].append(
                    score_benchmark_item(
                        item, cited, retrieval,
                        strategy=strat, latency_ms=dt,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - batch resilience
                err = f"generate_or_cite_failed: {type(exc).__name__}: {exc}"
                buckets[strat].append(
                    ItemEval(
                        question_id=item.query_id, question=item.query,
                        difficulty=item.difficulty, strategy=strat,
                        precision=0.0, recall=0.0, f1=0.0, coverage=0.0,
                        retrieval_recall_at_k=1.0,
                        n_answer_sentences=0,
                        n_gold_ids=len(item.gold_passage_ids), n_pred_ids=0,
                        retrieval=retrieval, error=err,
                    )
                )
        if on_progress is not None:
            on_progress(idx + 1, len(items), buckets)

    summaries: dict[Strategy, StrategyEvalSummary] = {
        s: summarize_strategy(buckets[s], s) for s in strategies
    }
    finished = datetime.now(timezone.utc)
    return EvalReport(
        rag_model=rag.model_identity,
        synth_model=synth.model_identity,
        judge_model=judge_b.model_identity,
        retrieval_mode="dual",
        k_sentences=0,
        k_chunks=0,
        tau=tau,
        top_k=top_k,
        strategies=summaries,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        elapsed_seconds=time.perf_counter() - t0,
    )


# ---------------------------------------------------------------------------
# HAGRID loader
# ---------------------------------------------------------------------------


def _extract_hagrid_gold_quote_ids(record: dict) -> set[str]:
    """Derive the set of quote ids humans marked as attribution evidence.

    HAGRID's annotation schema carries per-answer evidence spans. We
    accept several shapes (the format has drifted across releases):

    * Each answer may have an ``attributable`` list of quote ids.
    * Each answer may have a ``sentences`` list whose entries include
      ``attributable_quotes`` ids (nested).
    * Fall back to every quote mentioned anywhere under ``answers``.
    """
    ids: set[str] = set()
    for ans in record.get("answers", []) or []:
        for key in ("attributable", "quotes_used", "supporting_quotes"):
            vals = ans.get(key)
            if isinstance(vals, list):
                for v in vals:
                    if isinstance(v, (int, str)):
                        ids.add(str(v))
                    elif isinstance(v, dict):
                        qid = v.get("idx") or v.get("id") or v.get("quote_id")
                        if qid is not None:
                            ids.add(str(qid))
        for sent in ans.get("sentences", []) or []:
            for key in ("attributable_quotes", "supporting_quotes"):
                vals = sent.get(key)
                if isinstance(vals, list):
                    for v in vals:
                        if isinstance(v, (int, str)):
                            ids.add(str(v))
    return ids


def _pick_hagrid_answer(record: dict) -> str | None:
    """Pick the first ``answer`` string available from a HAGRID record."""
    for ans in record.get("answers", []) or []:
        txt = ans.get("answer") or ans.get("text")
        if isinstance(txt, str) and txt.strip():
            return txt.strip()
    return None


def load_hagrid_jsonl(
    path: Path | str, *, limit: int | None = None
) -> Iterator[BenchmarkItem]:
    """Stream HAGRID items from a JSONL release file.

    Skips records without quotes or without any resolvable gold
    attribution (can't be scored). Yields at most ``limit`` items
    when set.
    """
    path = Path(path)
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            query = record.get("query") or record.get("question")
            query_id = str(
                record.get("query_id")
                or record.get("id")
                or record.get("qid")
                or f"hagrid-{n:05d}"
            )
            quotes_raw = record.get("quotes") or record.get("passages") or []
            passages: list[Passage] = []
            for q in quotes_raw:
                qid = str(q.get("idx") or q.get("id") or q.get("quote_id") or len(passages))
                text = q.get("text") or q.get("quote") or ""
                if not text:
                    continue
                passages.append(
                    Passage(
                        passage_id=qid,
                        text=text,
                        title=q.get("title"),
                    )
                )

            gold_ids = _extract_hagrid_gold_quote_ids(record)
            gold_ids &= {p.passage_id for p in passages}

            if not query or not passages or not gold_ids:
                continue

            yield BenchmarkItem(
                query_id=query_id,
                query=query,
                passages=tuple(passages),
                gold_passage_ids=frozenset(gold_ids),
                gold_answer=_pick_hagrid_answer(record),
                source="hagrid",
            )
            n += 1
            if limit and n >= limit:
                return


# ---------------------------------------------------------------------------
# ALCE loader
# ---------------------------------------------------------------------------


def load_alce_jsonl(
    path: Path | str, *, limit: int | None = None
) -> Iterator[BenchmarkItem]:
    """Stream ALCE-format items (ASQA / ELI5 / QAMPARI).

    ALCE records carry ``docs: [{title, text, id, ...}]`` and either
    a precomputed ``answer`` plus ``citations`` (list of 0-based doc
    indices), or annotator-provided ``qa_pairs`` with ``wikipage``
    labels. We derive gold as every ``docs`` index referenced by a
    citation — this is the tightest faithful reading of ALCE's
    correctness check and aligns with the paper's set-level metric.
    """
    path = Path(path)
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            query = record.get("question") or record.get("query")
            query_id = str(
                record.get("id") or record.get("question_id") or f"alce-{n:05d}"
            )
            docs = record.get("docs") or []
            passages: list[Passage] = []
            for i, d in enumerate(docs):
                pid = str(d.get("id") or d.get("docid") or i)
                text = d.get("text") or d.get("snippet") or ""
                if not text:
                    continue
                passages.append(
                    Passage(
                        passage_id=pid,
                        text=text,
                        title=d.get("title"),
                    )
                )

            # Gold comes from answer.citations (0-based indices into docs)
            # or annotator-supplied citations list.
            gold_ids: set[str] = set()
            cit_idxs = record.get("citations") or record.get("gold_citations") or []
            for raw in cit_idxs:
                try:
                    idx = int(raw)
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < len(passages):
                    gold_ids.add(passages[idx].passage_id)

            if not query or not passages or not gold_ids:
                continue

            yield BenchmarkItem(
                query_id=query_id,
                query=query,
                passages=tuple(passages),
                gold_passage_ids=frozenset(gold_ids),
                gold_answer=record.get("answer"),
                source="alce",
            )
            n += 1
            if limit and n >= limit:
                return
