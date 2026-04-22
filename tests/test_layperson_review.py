"""Tests for sentcite.layperson_review + eval integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentcite.eval import ItemEval, StrategyEvalSummary, EvalReport, summarize_strategy
from sentcite.layperson_review import (
    FLAG_VOCAB,
    LaypersonReview,
    append_review,
    load_reviews,
    summarize_reviews,
    write_reviews,
)


def test_layperson_review_validates_confidence_and_role():
    with pytest.raises(ValueError):
        LaypersonReview(question_id="q", reviewer="r", reviewer_role="ml-engineer", confidence="uncertain")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        LaypersonReview(question_id="q", reviewer="r", reviewer_role="sme", confidence="high")  # type: ignore[arg-type]


def test_layperson_review_defaults_timestamp():
    r = LaypersonReview(
        question_id="q1", reviewer="jg", reviewer_role="ml-engineer",
        confidence="high",
    )
    assert r.reviewed_at.endswith("Z") and "T" in r.reviewed_at


def test_append_and_load_reviews_round_trip(tmp_path: Path):
    p = tmp_path / "reviews.jsonl"
    r1 = LaypersonReview("q1", "jg", "ml-engineer", "high")
    r2 = LaypersonReview("q2", "jg", "pm", "low", flags=("citation_mismatch",),
                         notes="cites wrong pub")
    append_review(p, r1)
    append_review(p, r2)
    loaded = load_reviews(p)
    assert set(loaded) == {"q1", "q2"}
    assert loaded["q2"].flags == ("citation_mismatch",)
    assert loaded["q2"].notes == "cites wrong pub"


def test_load_reviews_last_write_wins(tmp_path: Path):
    p = tmp_path / "reviews.jsonl"
    append_review(p, LaypersonReview("q1", "jg", "ml-engineer", "high"))
    append_review(p, LaypersonReview("q1", "jg", "ml-engineer", "low",
                                     notes="changed my mind"))
    loaded = load_reviews(p)
    assert loaded["q1"].confidence == "low"
    assert loaded["q1"].notes == "changed my mind"


def test_load_reviews_missing_file_returns_empty(tmp_path: Path):
    assert load_reviews(tmp_path / "nope.jsonl") == {}


def test_write_reviews_overwrites(tmp_path: Path):
    p = tmp_path / "reviews.jsonl"
    append_review(p, LaypersonReview("q1", "jg", "ml-engineer", "low"))
    write_reviews(p, [LaypersonReview("q2", "jg", "pm", "high")])
    loaded = load_reviews(p)
    assert set(loaded) == {"q2"}


def test_summarize_reviews_counts_by_confidence_and_flags():
    reviews = {
        "q1": LaypersonReview("q1", "jg", "ml-engineer", "high"),
        "q2": LaypersonReview("q2", "jg", "pm", "medium",
                              flags=("citation_mismatch", "out_of_scope")),
        "q3": LaypersonReview("q3", "jg", "ml-engineer", "low",
                              flags=("citation_mismatch",)),
    }
    s = summarize_reviews(reviews)
    assert s["total"] == 3
    assert s["by_confidence"] == {"high": 1, "medium": 1, "low": 1}
    assert s["flag_counts"]["citation_mismatch"] == 2
    assert list(s["flag_counts"].keys())[0] == "citation_mismatch"  # sorted desc


def test_flag_vocab_is_stable_controlled_list():
    assert "citation_mismatch" in FLAG_VOCAB
    assert "gold_answer_wrong" in FLAG_VOCAB


# ---------------------------------------------------------------------------
# Integration with eval.summarize_strategy
# ---------------------------------------------------------------------------


def _mk_item(qid: str, f1: float, conf: str | None) -> ItemEval:
    it = ItemEval(
        question_id=qid, question="q", difficulty="medium",
        strategy="inline_prompted",
        precision=f1, recall=f1, f1=f1,
        coverage=1.0, retrieval_recall_at_k=1.0,
        n_answer_sentences=1, n_gold_ids=1, n_pred_ids=1,
    )
    if conf is not None:
        it.reviewer_confidence = conf  # type: ignore[assignment]
        it.reviewer_role = "ml-engineer"
    return it


def test_summarize_strategy_bucketing_by_reviewer_confidence():
    items = [
        _mk_item("q1", 1.0, "high"),
        _mk_item("q2", 0.6, "high"),
        _mk_item("q3", 0.2, "low"),
        _mk_item("q4", 0.5, None),  # unreviewed — must not appear in any bucket
    ]
    summary = summarize_strategy(items, "inline_prompted")
    assert set(summary.by_reviewer_confidence) == {"high", "low"}
    assert summary.by_reviewer_confidence["high"]["n"] == 2.0
    assert summary.by_reviewer_confidence["high"]["f1"] == pytest.approx(0.8)
    assert summary.by_reviewer_confidence["low"]["n"] == 1.0
    assert summary.by_reviewer_confidence["low"]["f1"] == pytest.approx(0.2)


def test_item_eval_to_dict_includes_reviewer_fields_when_present():
    it = _mk_item("q1", 1.0, "high")
    it.reviewer_flags = ("citation_mismatch",)
    it.reviewer_notes = "off by one"
    d = it.to_dict()
    assert d["reviewer_confidence"] == "high"
    assert d["reviewer_flags"] == ["citation_mismatch"]
    assert d["reviewer_notes"] == "off by one"

    # Unreviewed item must NOT carry the keys (keeps historical runs clean).
    clean = _mk_item("q2", 0.5, None).to_dict()
    assert "reviewer_confidence" not in clean


def test_eval_report_renders_reviewer_section_only_when_reviewed():
    strat = summarize_strategy([_mk_item("q1", 1.0, None)], "inline_prompted")
    report = EvalReport(
        rag_model="rag", synth_model="synth", judge_model="judge",
        retrieval_mode="dual", k_sentences=20, k_chunks=5, tau=0.75, top_k=3,
        strategies={"inline_prompted": strat},
        started_at="t0", finished_at="t1", elapsed_seconds=1.0,
    )
    assert "reviewer confidence" not in report.to_markdown_table().lower()

    strat2 = summarize_strategy(
        [_mk_item("q1", 1.0, "high"), _mk_item("q2", 0.2, "low")],
        "inline_prompted",
    )
    report2 = EvalReport(
        rag_model="rag", synth_model="synth", judge_model="judge",
        retrieval_mode="dual", k_sentences=20, k_chunks=5, tau=0.75, top_k=3,
        strategies={"inline_prompted": strat2},
        started_at="t0", finished_at="t1", elapsed_seconds=1.0,
        reviews_summary={"total": 2, "by_confidence": {"high": 1, "medium": 0, "low": 1}, "flag_counts": {}},
    )
    md = report2.to_markdown_table()
    assert "reviewer confidence" in md.lower()
    assert "non-SME" in md or "not a substitute" in md.lower()
    assert "1.000 (n=1)" in md  # high bucket
    assert "0.200 (n=1)" in md  # low bucket
