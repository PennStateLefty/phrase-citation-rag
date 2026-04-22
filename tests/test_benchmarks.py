"""Tests for sentcite.benchmarks — passage-level adapter for HAGRID/ALCE."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sentcite.benchmarks import (
    BenchmarkItem,
    Passage,
    build_retrieval_result,
    evaluate_benchmark,
    load_alce_jsonl,
    load_hagrid_jsonl,
    parse_passage_id_from_chunk,
    predicted_passage_ids,
    score_benchmark_item,
)
from sentcite.schema import Citation, CitedAnswer, CitedSentence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _item() -> BenchmarkItem:
    return BenchmarkItem(
        query_id="q1",
        query="What is the 2025 standard mileage rate?",
        passages=(
            Passage("doc-a", "The 2025 rate is 70 cents per mile. Limitations apply."),
            Passage("doc-b", "Taxpayers may use the standard mileage rate. Details vary."),
            Passage("doc-c", "Unrelated prose about parking fees."),
        ),
        gold_passage_ids=frozenset({"doc-a", "doc-b"}),
    )


def _cit(sid: str) -> Citation:
    # chunk_id / document_id don't need to be realistic here — predicted_passage_ids
    # looks them up through the RetrievalResult, not from the Citation struct.
    return Citation(
        sentence_id=sid,
        chunk_id="ignored",
        document_id="ignored",
        page=1,
        section_path=[],
        confidence=0.9,
        source="llm",
    )


def _cited(per_sentence: list[list[str]]) -> CitedAnswer:
    return CitedAnswer(
        question="q",
        answer_text="a",
        sentences=[
            CitedSentence(
                index=i,
                text=f"s{i}",
                citations=[_cit(x) for x in ids],
            )
            for i, ids in enumerate(per_sentence)
        ],
        strategy="inline_prompted",
        model="gpt-4.1-1",
        retrieved_chunk_ids=[],
    )


# ---------------------------------------------------------------------------
# build_retrieval_result
# ---------------------------------------------------------------------------


def test_build_retrieval_result_shapes():
    item = _item()
    res = build_retrieval_result(item)
    assert res.mode == "dual"
    assert res.query == item.query
    assert len(res.chunks) == 3
    # 2 sentences in doc-a, 2 in doc-b, 1 in doc-c.
    assert len(res.sentence_candidates) == 5
    # Each chunk id is namespaced and monotonic.
    assert res.chunks[0].chunk_id == "bench::q1::p0000"
    assert res.chunks[2].chunk_id == "bench::q1::p0002"
    # document_id preserves the caller's passage id.
    assert res.chunks[0].document_id == "doc-a"
    assert res.sentence_candidates[0].document_id == "doc-a"
    # Every sentence has a unique id of the expected shape.
    sids = [s.sentence_id for s in res.sentence_candidates]
    assert len(sids) == len(set(sids))
    assert all(s.startswith("bench::q1::p") for s in sids)


def test_build_retrieval_result_passage_without_splittable_text_yields_one_sentence():
    item = BenchmarkItem(
        query_id="q", query="q",
        passages=(Passage("d", "singleword"),),
        gold_passage_ids=frozenset({"d"}),
    )
    res = build_retrieval_result(item)
    assert len(res.sentence_candidates) == 1
    assert res.sentence_candidates[0].text == "singleword"


def test_parse_passage_id_from_chunk():
    assert parse_passage_id_from_chunk("bench::q1::p0003") == "p0003"
    assert parse_passage_id_from_chunk("bench::q1::p0003::s002") == "p0003"
    assert parse_passage_id_from_chunk("other::x") is None
    assert parse_passage_id_from_chunk("bench::only") is None


# ---------------------------------------------------------------------------
# predicted_passage_ids + score_benchmark_item
# ---------------------------------------------------------------------------


def test_predicted_passage_ids_maps_sids_to_original_passage_ids():
    item = _item()
    retrieval = build_retrieval_result(item)

    # Cite the first sentence of doc-a and the first of doc-c.
    doc_a_sid = retrieval.sentence_candidates[0].sentence_id
    doc_c_sid = next(
        s.sentence_id for s in retrieval.sentence_candidates if s.document_id == "doc-c"
    )
    cited = _cited([[doc_a_sid, doc_c_sid]])

    assert predicted_passage_ids(cited, retrieval) == {"doc-a", "doc-c"}


def test_predicted_passage_ids_ignores_unknown_sids():
    item = _item()
    retrieval = build_retrieval_result(item)
    cited = _cited([["not-a-real-sid"]])
    assert predicted_passage_ids(cited, retrieval) == set()


def test_score_benchmark_item_passage_prf_and_coverage():
    item = _item()
    retrieval = build_retrieval_result(item)
    a_sid = retrieval.sentence_candidates[0].sentence_id  # doc-a
    c_sid = next(
        s.sentence_id for s in retrieval.sentence_candidates if s.document_id == "doc-c"
    )
    cited = _cited([[a_sid, c_sid], []])  # pred={doc-a,doc-c}, gold={doc-a,doc-b}

    it = score_benchmark_item(
        item, cited, retrieval, strategy="inline_prompted", latency_ms=5.0
    )
    # tp=1, pred=2, gold=2 → p=0.5, r=0.5, f1=0.5.
    assert it.precision == 0.5
    assert it.recall == 0.5
    assert it.f1 == 0.5
    assert it.coverage == 0.5  # 1 of 2 answer sentences cited
    assert it.retrieval_recall_at_k == 1.0  # vacuous for benchmark
    assert it.difficulty == "medium"


# ---------------------------------------------------------------------------
# evaluate_benchmark (mocked generate + cite_answer)
# ---------------------------------------------------------------------------


def test_evaluate_benchmark_runs_both_strategies_and_aggregates():
    items = [_item()]
    rag = SimpleNamespace(model_identity="gpt-4.1-1", deployment="gpt-4.1-1")
    synth = SimpleNamespace(model_identity="mistral-large-3", deployment="m")
    judge_b = SimpleNamespace(model_identity="llama-3.3-70b-instruct", deployment="l")

    def _binding(role, cfg=None):
        return {"rag": rag, "synth_gt": synth, "judge": judge_b}[role]

    # We'll have cite_answer deterministically pick the first sid of doc-a
    # under Strategy A (f1 = 2/3 given gold {doc-a, doc-b}) and both doc-a
    # and doc-b first sids under Strategy B (f1 = 1.0).
    pending: dict[str, CitedAnswer] = {}

    def _cite_side_effect(gen, retrieval, **kwargs):
        a_sid = retrieval.sentence_candidates[0].sentence_id
        b_sid = next(
            s.sentence_id for s in retrieval.sentence_candidates
            if s.document_id == "doc-b"
        )
        # Order: A first, then B — mirrors the harness loop.
        if "a_done" not in pending:
            pending["a_done"] = True
            return _cited([[a_sid]])
        return _cited([[a_sid, b_sid]])

    with patch("sentcite.benchmarks.get_binding", side_effect=_binding), \
         patch("sentcite.benchmarks.get_client", return_value=MagicMock()), \
         patch("sentcite.benchmarks.generate"), \
         patch("sentcite.benchmarks.cite_answer", side_effect=_cite_side_effect):
        report = evaluate_benchmark(items)

    a = report.strategies["inline_prompted"]
    b = report.strategies["post_gen_alignment"]

    # Strategy A: pred={doc-a}, gold={doc-a,doc-b} → p=1.0, r=0.5, f1=2/3.
    assert a.macro_precision == 1.0
    assert a.macro_recall == 0.5
    assert a.macro_f1 == pytest.approx(2 / 3)
    # Strategy B: pred={doc-a,doc-b} == gold → perfect.
    assert b.macro_f1 == 1.0


def test_evaluate_benchmark_survives_generate_failure():
    items = [_item()]
    rag = SimpleNamespace(model_identity="m", deployment="m")

    def _binding(role, cfg=None):
        return rag

    def _boom(*args, **kwargs):
        raise RuntimeError("content_filter")

    with patch("sentcite.benchmarks.get_binding", side_effect=_binding), \
         patch("sentcite.benchmarks.get_client", return_value=MagicMock()), \
         patch("sentcite.benchmarks.generate", side_effect=_boom):
        report = evaluate_benchmark(items, strategies=("inline_prompted",))

    it = report.strategies["inline_prompted"].items[0]
    assert it.f1 == 0.0
    assert "content_filter" in it.error


# ---------------------------------------------------------------------------
# HAGRID loader
# ---------------------------------------------------------------------------


def test_load_hagrid_jsonl_parses_quotes_and_attribution(tmp_path: Path):
    records = [
        {
            "query_id": "h1",
            "query": "Who painted the Mona Lisa?",
            "quotes": [
                {"idx": "q0", "text": "Leonardo da Vinci painted the Mona Lisa."},
                {"idx": "q1", "text": "It hangs in the Louvre."},
                {"idx": "q2", "text": "Unrelated trivia about pigeons."},
            ],
            "answers": [
                {
                    "answer": "Leonardo da Vinci.",
                    "attributable": ["q0", "q1"],
                }
            ],
        },
        {
            # Missing gold -> skipped.
            "query_id": "h2",
            "query": "What?",
            "quotes": [{"idx": "x", "text": "t"}],
            "answers": [],
        },
        {
            # Gold references a quote not in the list -> dropped from gold set
            # and record still skipped (no remaining gold).
            "query_id": "h3",
            "query": "Q?",
            "quotes": [{"idx": "q0", "text": "one"}],
            "answers": [{"answer": "a", "attributable": ["ghost"]}],
        },
    ]
    path = tmp_path / "hagrid.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))

    items = list(load_hagrid_jsonl(path))
    assert len(items) == 1
    it = items[0]
    assert it.query_id == "h1"
    assert {p.passage_id for p in it.passages} == {"q0", "q1", "q2"}
    assert it.gold_passage_ids == frozenset({"q0", "q1"})
    assert it.gold_answer == "Leonardo da Vinci."
    assert it.source == "hagrid"


def test_load_hagrid_jsonl_nested_sentence_attribution(tmp_path: Path):
    record = {
        "query_id": "h",
        "query": "q?",
        "quotes": [
            {"idx": 0, "text": "p0"},
            {"idx": 1, "text": "p1"},
        ],
        "answers": [
            {
                "answer": "a",
                "sentences": [
                    {"attributable_quotes": [1]},
                    {"attributable_quotes": [0, 1]},
                ],
            }
        ],
    }
    path = tmp_path / "hagrid.jsonl"
    path.write_text(json.dumps(record))
    items = list(load_hagrid_jsonl(path))
    assert len(items) == 1
    assert items[0].gold_passage_ids == frozenset({"0", "1"})


def test_load_hagrid_jsonl_limit(tmp_path: Path):
    records = [
        {
            "query_id": f"h{i}", "query": "q?",
            "quotes": [{"idx": "q0", "text": "t"}],
            "answers": [{"answer": "a", "attributable": ["q0"]}],
        }
        for i in range(5)
    ]
    path = tmp_path / "hagrid.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))
    items = list(load_hagrid_jsonl(path, limit=2))
    assert len(items) == 2


# ---------------------------------------------------------------------------
# ALCE loader
# ---------------------------------------------------------------------------


def test_load_alce_jsonl_parses_docs_and_citation_indices(tmp_path: Path):
    record = {
        "id": "asqa-1",
        "question": "What are some rivers?",
        "docs": [
            {"id": "d0", "title": "Amazon", "text": "The Amazon River is in South America."},
            {"id": "d1", "title": "Nile", "text": "The Nile flows through Egypt."},
            {"id": "d2", "title": "Irrelevant", "text": "Cats are small furry animals."},
        ],
        "answer": "The Amazon and Nile are two rivers.",
        "citations": [0, 1],
    }
    path = tmp_path / "alce.jsonl"
    path.write_text(json.dumps(record))
    items = list(load_alce_jsonl(path))
    assert len(items) == 1
    it = items[0]
    assert it.query_id == "asqa-1"
    assert it.gold_passage_ids == frozenset({"d0", "d1"})
    assert it.source == "alce"


def test_load_alce_jsonl_skips_records_with_no_gold(tmp_path: Path):
    record = {
        "id": "x", "question": "q?",
        "docs": [{"id": "d0", "text": "t"}],
        "citations": [],
    }
    path = tmp_path / "alce.jsonl"
    path.write_text(json.dumps(record))
    assert list(load_alce_jsonl(path)) == []
