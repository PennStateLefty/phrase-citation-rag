"""Tests for sentcite.eval — pure metrics, aggregation, and mocked orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sentcite.eval import (
    EvalReport,
    ItemEval,
    StrategyEvalSummary,
    coverage,
    evaluate_gt_set,
    flatten_gold_ids,
    flatten_pred_ids,
    prf,
    retrieval_recall,
    retrieval_sid_pool,
    score_item,
    summarize_strategy,
    write_eval_report,
)
from sentcite.retrieval import ChunkHit, RetrievalResult, SentenceHit
from sentcite.schema import Citation, CitedAnswer, CitedSentence, GroundTruthItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _cit(sid: str) -> Citation:
    return Citation(
        sentence_id=sid,
        chunk_id="doc1-c01",
        document_id="doc1",
        page=1,
        section_path=[],
        confidence=0.9,
        source="llm",
    )


def _cited(per_sentence: list[list[str]]) -> CitedAnswer:
    sentences = [
        CitedSentence(
            index=i,
            text=f"answer sentence {i}.",
            citations=[_cit(sid) for sid in ids],
        )
        for i, ids in enumerate(per_sentence)
    ]
    return CitedAnswer(
        question="q",
        answer_text=" ".join(s.text for s in sentences),
        sentences=sentences,
        strategy="inline_prompted",
        model="gpt-4.1-1",
        retrieved_chunk_ids=["doc1-c01"],
    )


def _gt(
    qid: str,
    difficulty: str,
    gold: list[list[str]],
) -> GroundTruthItem:
    return GroundTruthItem(
        question_id=qid,
        question=f"Question {qid}",
        difficulty=difficulty,
        gold_answer="Gold answer sentence.",
        gold_citations=gold,
    )


def _result_with_pool(sids: list[str]) -> RetrievalResult:
    # Put the first half in Layout Y, the rest nested in a Layout X chunk.
    mid = len(sids) // 2
    cands = [
        SentenceHit(
            sentence_id=s, chunk_id="c1", document_id="doc1", page=1,
            section_path=[], text="x",
        )
        for s in sids[:mid]
    ]
    chunk = ChunkHit(
        chunk_id="c2", document_id="doc1", page=2, section_path=[],
        text="chunk text", token_count=10,
        sentences=[{"sentence_id": s, "text": "x"} for s in sids[mid:]],
        source="chunk_search",
    )
    return RetrievalResult(
        query="q", mode="dual", chunks=[chunk], sentence_candidates=cands,
    )


# ---------------------------------------------------------------------------
# Pure metric helpers
# ---------------------------------------------------------------------------


def test_flatten_gold_and_pred_ids():
    gt = _gt("q1", "easy", [["a", "b"], ["b", "c"]])
    assert flatten_gold_ids(gt) == {"a", "b", "c"}
    cited = _cited([["a", "b"], ["c"], []])
    assert flatten_pred_ids(cited) == {"a", "b", "c"}


def test_retrieval_sid_pool_unions_both_layouts():
    res = _result_with_pool(["a", "b", "c", "d"])
    assert retrieval_sid_pool(res) == {"a", "b", "c", "d"}


def test_prf_perfect():
    p, r, f = prf({"a", "b"}, {"a", "b"})
    assert (p, r, f) == (1.0, 1.0, 1.0)


def test_prf_partial():
    # pred={a,b}, gold={b,c}: tp=1, precision=0.5, recall=0.5, f1=0.5
    p, r, f = prf({"a", "b"}, {"b", "c"})
    assert p == 0.5 and r == 0.5 and f == 0.5


def test_prf_disjoint_and_empty_edges():
    assert prf({"a"}, {"b"}) == (0.0, 0.0, 0.0)
    assert prf(set(), set()) == (1.0, 1.0, 1.0)
    assert prf(set(), {"a"}) == (0.0, 0.0, 0.0)
    assert prf({"a"}, set()) == (0.0, 0.0, 0.0)


def test_coverage_mixed():
    cited = _cited([["a"], [], ["b"]])
    assert coverage(cited) == pytest.approx(2 / 3)


def test_coverage_empty_answer():
    cited = _cited([])
    assert coverage(cited) == 0.0


def test_retrieval_recall_all_present():
    res = _result_with_pool(["a", "b", "c"])
    assert retrieval_recall({"a", "c"}, res) == 1.0


def test_retrieval_recall_missing_half():
    res = _result_with_pool(["a", "b"])
    assert retrieval_recall({"a", "x", "y"}, res) == pytest.approx(1 / 3)


def test_retrieval_recall_empty_gold_is_vacuous_1():
    res = _result_with_pool([])
    assert retrieval_recall(set(), res) == 1.0


# ---------------------------------------------------------------------------
# score_item
# ---------------------------------------------------------------------------


def test_score_item_composes_all_metrics():
    gt = _gt("q1", "medium", [["a", "b"], ["c"]])
    cited = _cited([["a", "b"], ["x"]])  # pred = {a,b,x}, gold = {a,b,c}
    result = _result_with_pool(["a", "b", "c", "d"])
    it = score_item(gt, cited, result, strategy="inline_prompted", latency_ms=42.0)

    # tp=2 (a,b), pred=3, gold=3 → p=2/3, r=2/3, f1=2/3
    assert it.precision == pytest.approx(2 / 3)
    assert it.recall == pytest.approx(2 / 3)
    assert it.f1 == pytest.approx(2 / 3)
    assert it.coverage == 1.0  # both answer sentences cited
    assert it.retrieval_recall_at_k == 1.0  # all gold sids in pool
    assert it.n_gold_ids == 3
    assert it.n_pred_ids == 3
    assert it.latency_ms == 42.0
    assert it.strategy == "inline_prompted"
    assert it.difficulty == "medium"


# ---------------------------------------------------------------------------
# summarize_strategy + to_dict + markdown
# ---------------------------------------------------------------------------


def _item(
    qid: str, diff: str, p: float, r: float, f: float, cov: float, rr: float,
    strategy: str = "inline_prompted",
) -> ItemEval:
    return ItemEval(
        question_id=qid, question="q", difficulty=diff,
        strategy=strategy,
        precision=p, recall=r, f1=f, coverage=cov,
        retrieval_recall_at_k=rr,
        n_answer_sentences=1, n_gold_ids=1, n_pred_ids=1,
    )


def test_summarize_strategy_macro_and_per_difficulty():
    items = [
        _item("q1", "easy", 1.0, 1.0, 1.0, 1.0, 1.0),
        _item("q2", "easy", 0.5, 0.5, 0.5, 0.5, 1.0),
        _item("q3", "hard", 0.0, 0.0, 0.0, 0.0, 0.5),
    ]
    s = summarize_strategy(items, "inline_prompted")
    assert s.macro_precision == pytest.approx(0.5)
    assert s.macro_f1 == pytest.approx(0.5)
    assert s.macro_coverage == pytest.approx(0.5)
    assert s.macro_retrieval_recall_at_k == pytest.approx(5 / 6)
    assert s.by_difficulty["easy"]["f1"] == 0.75
    assert s.by_difficulty["easy"]["n"] == 2.0
    assert s.by_difficulty["hard"]["f1"] == 0.0


def test_item_eval_to_dict_includes_pred_citations():
    cited = _cited([["a", "b"]])
    it = ItemEval(
        question_id="q1", question="q", difficulty="easy",
        strategy="inline_prompted",
        precision=1.0, recall=1.0, f1=1.0, coverage=1.0,
        retrieval_recall_at_k=1.0,
        n_answer_sentences=1, n_gold_ids=2, n_pred_ids=2,
        cited=cited,
    )
    d = it.to_dict()
    assert d["pred_citation_ids"] == ["a", "b"]
    assert "answer_text" in d


def test_eval_report_markdown_side_by_side():
    items_a = [_item("q1", "easy", 1.0, 1.0, 1.0, 1.0, 1.0, strategy="inline_prompted")]
    items_b = [_item("q1", "easy", 0.5, 0.5, 0.5, 1.0, 1.0, strategy="post_gen_alignment")]
    report = EvalReport(
        rag_model="gpt-4.1-1", synth_model="mistral-large-3",
        judge_model="llama-3.3-70b-instruct",
        retrieval_mode="dual", k_sentences=20, k_chunks=5,
        tau=0.75, top_k=3,
        strategies={
            "inline_prompted": summarize_strategy(items_a, "inline_prompted"),
            "post_gen_alignment": summarize_strategy(items_b, "post_gen_alignment"),
        },
        started_at="t0", finished_at="t1", elapsed_seconds=12.3,
    )
    md = report.to_markdown_table()
    assert "Precision" in md and "Recall" in md and "F1" in md
    assert "inline_prompted" in md and "post_gen_alignment" in md
    assert "1.000" in md and "0.500" in md
    # Faithfulness + Stability are populated as 'n/a' when absent.
    assert "Faithful %" in md and "Stability" in md
    assert "n/a" in md
    # Per-difficulty section.
    assert "F1 by difficulty" in md
    assert "easy" in md


# ---------------------------------------------------------------------------
# evaluate_gt_set orchestration (mocked)
# ---------------------------------------------------------------------------


def test_evaluate_gt_set_runs_both_strategies_with_shared_retrieval():
    gts = [
        _gt("q1", "easy", [["a"]]),
        _gt("q2", "medium", [["b", "c"]]),
    ]

    rag = SimpleNamespace(model_identity="gpt-4.1-1", deployment="gpt-4.1-1")
    synth = SimpleNamespace(model_identity="mistral-large-3", deployment="M")
    judge_b = SimpleNamespace(model_identity="llama-3.3-70b-instruct", deployment="L")

    def _binding(role, cfg=None):
        return {"rag": rag, "synth_gt": synth, "judge": judge_b}[role]

    # Every retrieve returns a pool containing the gold for that item.
    def _fake_retrieve(question, **kwargs):
        if question.endswith("q1"):
            return _result_with_pool(["a", "z"])
        return _result_with_pool(["b", "c", "z"])

    # Strategy A cites gold perfectly; Strategy B cites one extra spurious id.
    cite_outputs = [
        _cited([["a"]]),            # q1, A
        _cited([["a", "x"]]),       # q1, B
        _cited([["b", "c"]]),       # q2, A
        _cited([["b"]]),            # q2, B
    ]

    with patch("sentcite.eval.get_binding", side_effect=_binding), \
         patch("sentcite.eval.get_client", return_value=MagicMock()), \
         patch("sentcite.eval.retrieve", side_effect=_fake_retrieve) as mock_ret, \
         patch("sentcite.eval.generate") as mock_gen, \
         patch("sentcite.eval.cite_answer", side_effect=cite_outputs):
        mock_gen.return_value = SimpleNamespace()
        report = evaluate_gt_set(gts)

    # Retrieve is called once per GT item (shared across strategies).
    assert mock_ret.call_count == 2
    # generate is called 2 items × 2 strategies = 4 times.
    assert mock_gen.call_count == 4

    assert set(report.strategies) == {"inline_prompted", "post_gen_alignment"}
    a = report.strategies["inline_prompted"]
    b = report.strategies["post_gen_alignment"]

    # A is perfect on both (pred == gold).
    assert a.macro_f1 == 1.0
    assert a.macro_precision == 1.0
    assert a.macro_recall == 1.0
    # B: q1 → pred {a,x}, gold {a}: p=0.5, r=1.0, f1=2/3.
    # B: q2 → pred {b},   gold {b,c}: p=1.0, r=0.5, f1=2/3.
    # Macro F1 = 2/3.
    assert b.macro_f1 == pytest.approx(2 / 3)


def test_evaluate_gt_set_resilient_to_generate_failure():
    """A single bad item must not abort the entire batch."""
    gts = [
        _gt("q1", "easy", [["a"]]),
        _gt("q2", "medium", [["b"]]),
    ]
    rag = SimpleNamespace(model_identity="gpt-4.1-1", deployment="gpt-4.1-1")

    def _binding(role, cfg=None):
        return rag

    def _gen(question, result, **kwargs):
        if "q2" in question:
            raise RuntimeError("content_filter")
        return SimpleNamespace()

    with patch("sentcite.eval.get_binding", side_effect=_binding), \
         patch("sentcite.eval.get_client", return_value=MagicMock()), \
         patch("sentcite.eval.retrieve", return_value=_result_with_pool(["a", "b"])), \
         patch("sentcite.eval.generate", side_effect=_gen), \
         patch("sentcite.eval.cite_answer", side_effect=[_cited([["a"]]), _cited([["a"]])]):
        report = evaluate_gt_set(gts, strategies=("inline_prompted",))

    items = report.strategies["inline_prompted"].items
    assert len(items) == 2
    assert items[0].error is None and items[0].f1 == 1.0
    assert items[1].error is not None and items[1].f1 == 0.0
    assert "content_filter" in items[1].error


def test_evaluate_gt_set_resilient_to_retrieve_failure():
    gts = [_gt("q1", "easy", [["a"]])]
    rag = SimpleNamespace(model_identity="m", deployment="m")

    def _binding(role, cfg=None):
        return rag

    with patch("sentcite.eval.get_binding", side_effect=_binding), \
         patch("sentcite.eval.get_client", return_value=MagicMock()), \
         patch("sentcite.eval.retrieve", side_effect=RuntimeError("search down")):
        report = evaluate_gt_set(gts, strategies=("inline_prompted",))

    items = report.strategies["inline_prompted"].items
    assert len(items) == 1
    assert "retrieve_failed" in items[0].error
    assert items[0].f1 == 0.0
    gts = [_gt("q1", "easy", [["a"]])]
    rag = SimpleNamespace(model_identity="m", deployment="m")

    def _binding(role, cfg=None):
        return rag

    with patch("sentcite.eval.get_binding", side_effect=_binding), \
         patch("sentcite.eval.get_client", return_value=MagicMock()), \
         patch("sentcite.eval.retrieve", return_value=_result_with_pool(["a"])), \
         patch("sentcite.eval.generate"), \
         patch("sentcite.eval.cite_answer", side_effect=[_cited([["a"]]), _cited([["a"]])]):
        calls = []
        evaluate_gt_set(gts, on_progress=lambda i, n, buckets: calls.append((i, n)))
        assert calls == [(1, 1)]


# ---------------------------------------------------------------------------
# write_eval_report round-trip
# ---------------------------------------------------------------------------


def test_write_eval_report_persists_items_manifest_and_summary(tmp_path: Path):
    items_a = [_item("q1", "easy", 1.0, 1.0, 1.0, 1.0, 1.0, strategy="inline_prompted")]
    items_b = [_item("q1", "easy", 0.5, 0.5, 0.5, 1.0, 1.0, strategy="post_gen_alignment")]
    # Attach a cited object so to_dict emits pred ids.
    items_a[0].cited = _cited([["a"]])

    report = EvalReport(
        rag_model="gpt-4.1-1", synth_model="mistral-large-3",
        judge_model="llama-3.3-70b-instruct",
        retrieval_mode="dual", k_sentences=20, k_chunks=5,
        tau=0.75, top_k=3,
        strategies={
            "inline_prompted": summarize_strategy(items_a, "inline_prompted"),
            "post_gen_alignment": summarize_strategy(items_b, "post_gen_alignment"),
        },
        started_at="t0", finished_at="t1", elapsed_seconds=5.0,
    )

    paths = write_eval_report(report, out_dir=tmp_path, run_id="eval-test")
    assert paths["items"].exists()
    assert paths["manifest"].exists()
    assert paths["summary"].exists()

    # 2 items (1 per strategy) → 2 lines.
    lines = paths["items"].read_text().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert {p["strategy"] for p in parsed} == {"inline_prompted", "post_gen_alignment"}

    manifest = json.loads(paths["manifest"].read_text())
    assert manifest["run_id"] == "eval-test"
    assert manifest["strategies"]["inline_prompted"]["macro_f1"] == 1.0

    summary_md = paths["summary"].read_text()
    assert "# Phase 1a evaluation" in summary_md
    assert "Strategy comparison" in summary_md
    assert "gpt-4.1-1" in summary_md
