"""Tests for sentcite.self_consistency — pure helpers + mocked orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sentcite.retrieval import RetrievalResult
from sentcite.schema import Citation, CitedAnswer, CitedSentence
from sentcite.self_consistency import (
    ReplicaRun,
    StabilityBatch,
    StabilityReport,
    build_report_from_replicas,
    citation_frequency,
    citation_id_set,
    intersection_union,
    mean_pairwise_jaccard,
    run_self_consistency,
    run_self_consistency_batch,
    stable_anchor_ids,
    write_stability_batch,
)


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


def _cited(sentence_lists: list[list[str]]) -> CitedAnswer:
    """Build a CitedAnswer from [[sid, sid], [sid], ...]."""
    sentences = [
        CitedSentence(
            index=i,
            text=f"answer sentence {i}.",
            citations=[_cit(sid) for sid in ids],
        )
        for i, ids in enumerate(sentence_lists)
    ]
    return CitedAnswer(
        question="q",
        answer_text=" ".join(s.text for s in sentences),
        sentences=sentences,
        strategy="inline_prompted",
        model="gpt-4.1-1",
        retrieved_chunk_ids=["doc1-c01"],
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_citation_id_set_flattens_and_dedupes():
    cited = _cited([["a", "b"], ["b", "c"], []])
    assert citation_id_set(cited) == {"a", "b", "c"}


def test_citation_id_set_empty_answer():
    cited = _cited([[]])
    assert citation_id_set(cited) == set()


def test_intersection_union_multi():
    sets = [{"a", "b"}, {"b", "c"}, {"b", "d"}]
    inter, union = intersection_union(sets)
    assert inter == {"b"}
    assert union == {"a", "b", "c", "d"}


def test_intersection_union_single():
    inter, union = intersection_union([{"a", "b"}])
    assert inter == {"a", "b"}
    assert union == {"a", "b"}


def test_intersection_union_empty_sequence():
    inter, union = intersection_union([])
    assert inter == set()
    assert union == set()


def test_mean_pairwise_jaccard_identical():
    sets = [{"a", "b"}, {"a", "b"}, {"a", "b"}]
    assert mean_pairwise_jaccard(sets) == 1.0


def test_mean_pairwise_jaccard_disjoint():
    sets = [{"a"}, {"b"}, {"c"}]
    assert mean_pairwise_jaccard(sets) == 0.0


def test_mean_pairwise_jaccard_partial():
    # Pair (A,B): |{b}|/|{a,b,c}| = 1/3
    # Pair (A,C): |{b}|/|{a,b,d}| = 1/3
    # Pair (B,C): |{b}|/|{b,c,d}| = 1/3
    sets = [{"a", "b"}, {"b", "c"}, {"b", "d"}]
    assert mean_pairwise_jaccard(sets) == pytest.approx(1 / 3)


def test_mean_pairwise_jaccard_fewer_than_two():
    assert mean_pairwise_jaccard([]) == 1.0
    assert mean_pairwise_jaccard([{"a"}]) == 1.0


def test_mean_pairwise_jaccard_all_empty():
    assert mean_pairwise_jaccard([set(), set(), set()]) == 1.0


def test_citation_frequency_counts():
    sets = [{"a", "b"}, {"b", "c"}, {"b", "d"}]
    assert citation_frequency(sets) == {"a": 1, "b": 3, "c": 1, "d": 1}


def test_stable_anchor_ids_majority_threshold():
    # 5 runs, majority threshold (0.5) → ceil(2.5)=3
    freq = {"a": 5, "b": 3, "c": 2, "d": 1}
    anchors = stable_anchor_ids(freq, n_runs=5, threshold=0.5)
    assert anchors == ["a", "b"]  # only those with freq >= 3


def test_stable_anchor_ids_sorted_by_freq_then_id():
    # n_runs=5, threshold=0.5 → cutoff=ceil(2.5)=3; both z and a qualify.
    freq = {"z": 4, "a": 4, "m": 2}
    anchors = stable_anchor_ids(freq, n_runs=5, threshold=0.5)
    # Both at 4; alphabetical tie-break puts a first.
    assert anchors == ["a", "z"]


def test_stable_anchor_ids_min_cutoff_one():
    # Tight threshold would round down to 0; we enforce floor of 1.
    freq = {"a": 1}
    anchors = stable_anchor_ids(freq, n_runs=1, threshold=0.01)
    assert anchors == ["a"]


# ---------------------------------------------------------------------------
# build_report_from_replicas
# ---------------------------------------------------------------------------


def _replica(run_index: int, per_sentence: list[list[str]]) -> ReplicaRun:
    return ReplicaRun.from_cited(
        run_index=run_index,
        temperature=0.7,
        cited=_cited(per_sentence),
        latency_ms=123.0,
    )


def test_report_perfect_stability():
    replicas = [_replica(i, [["a", "b"]]) for i in range(3)]
    rep = build_report_from_replicas(
        question="q",
        strategy="inline_prompted",
        temperature=0.7,
        rag_model="gpt-4.1-1",
        retrieval_mode="dual",
        replicas=replicas,
    )
    assert rep.stability == 1.0
    assert rep.mean_pairwise_jaccard == 1.0
    assert rep.union_ids == ["a", "b"]
    assert rep.intersection_ids == ["a", "b"]
    assert rep.frequency == {"a": 3, "b": 3}
    assert rep.stable_anchors == ["a", "b"]
    assert rep.coverage_rate == 1.0


def test_report_complete_drift():
    replicas = [
        _replica(0, [["a"]]),
        _replica(1, [["b"]]),
        _replica(2, [["c"]]),
    ]
    rep = build_report_from_replicas(
        question="q",
        strategy="inline_prompted",
        temperature=0.7,
        rag_model="gpt-4.1-1",
        retrieval_mode="dual",
        replicas=replicas,
    )
    assert rep.stability == 0.0
    assert rep.intersection_ids == []
    assert sorted(rep.union_ids) == ["a", "b", "c"]
    assert rep.stable_anchors == []  # nothing reaches majority


def test_report_partial_drift():
    # All cite 'a', plus run0 cites 'b', run1 cites 'c', run2 cites 'd'.
    replicas = [
        _replica(0, [["a", "b"]]),
        _replica(1, [["a", "c"]]),
        _replica(2, [["a", "d"]]),
    ]
    rep = build_report_from_replicas(
        question="q",
        strategy="inline_prompted",
        temperature=0.7,
        rag_model="gpt-4.1-1",
        retrieval_mode="dual",
        replicas=replicas,
    )
    assert rep.stability == pytest.approx(1 / 4)  # |{a}|/|{a,b,c,d}|
    assert rep.intersection_ids == ["a"]
    assert rep.stable_anchors == ["a"]  # only a appears in majority


def test_report_per_sentence_jaccard_when_shape_matches():
    # Two answer sentences; sentence 0 stable, sentence 1 drifts.
    replicas = [
        _replica(0, [["a"], ["b"]]),
        _replica(1, [["a"], ["c"]]),
    ]
    rep = build_report_from_replicas(
        question="q",
        strategy="inline_prompted",
        temperature=0.7,
        rag_model="gpt-4.1-1",
        retrieval_mode="dual",
        replicas=replicas,
    )
    assert rep.per_sentence_mean_jaccard == [1.0, 0.0]


def test_report_per_sentence_none_when_shape_differs():
    replicas = [
        _replica(0, [["a"], ["b"]]),
        _replica(1, [["a"]]),  # different sentence count
    ]
    rep = build_report_from_replicas(
        question="q",
        strategy="inline_prompted",
        temperature=0.7,
        rag_model="gpt-4.1-1",
        retrieval_mode="dual",
        replicas=replicas,
    )
    assert rep.per_sentence_mean_jaccard is None


def test_report_coverage_rate_mix():
    # 2 of 3 runs have citations, 1 is empty.
    replicas = [
        _replica(0, [["a"]]),
        _replica(1, [["a"]]),
        _replica(2, [[]]),
    ]
    rep = build_report_from_replicas(
        question="q",
        strategy="inline_prompted",
        temperature=0.7,
        rag_model="gpt-4.1-1",
        retrieval_mode="dual",
        replicas=replicas,
    )
    assert rep.coverage_rate == pytest.approx(2 / 3)


def test_report_to_dict_round_trip():
    replicas = [_replica(i, [["a", "b"]]) for i in range(2)]
    rep = build_report_from_replicas(
        question="q",
        strategy="inline_prompted",
        temperature=0.7,
        rag_model="gpt-4.1-1",
        retrieval_mode="dual",
        replicas=replicas,
    )
    d = rep.to_dict()
    roundtrip = json.loads(json.dumps(d))
    assert roundtrip["stability"] == 1.0
    assert roundtrip["n_runs"] == 2
    assert len(roundtrip["runs"]) == 2
    assert roundtrip["runs"][0]["citation_ids"] == ["a", "b"]


# ---------------------------------------------------------------------------
# run_self_consistency with mocked generate + cite_answer + retrieve
# ---------------------------------------------------------------------------


def _empty_result() -> RetrievalResult:
    return RetrievalResult(query="q", mode="dual")


def test_run_self_consistency_invokes_n_times_with_temperature():
    # cite_answer returns a rotating set of citations per run.
    answers = [
        _cited([["a", "b"]]),
        _cited([["a", "c"]]),
        _cited([["a", "d"]]),
    ]
    rag_binding = SimpleNamespace(model_identity="gpt-4.1-1", deployment="gpt-4.1-1")

    with patch(
        "sentcite.self_consistency.get_binding", return_value=rag_binding
    ), patch(
        "sentcite.self_consistency.get_client", return_value=MagicMock()
    ), patch(
        "sentcite.self_consistency.retrieve", return_value=_empty_result()
    ) as mock_ret, patch(
        "sentcite.self_consistency.generate"
    ) as mock_gen, patch(
        "sentcite.self_consistency.cite_answer", side_effect=answers
    ):
        mock_gen.return_value = SimpleNamespace()
        rep = run_self_consistency(
            "q",
            strategy="inline_prompted",
            n_runs=3,
            temperature=0.7,
        )

    assert mock_ret.call_count == 1  # retrieval done once
    assert mock_gen.call_count == 3
    for call in mock_gen.call_args_list:
        assert call.kwargs["temperature"] == 0.7
        assert call.kwargs["strategy"] == "inline_prompted"

    assert rep.n_runs == 3
    assert rep.intersection_ids == ["a"]
    assert sorted(rep.union_ids) == ["a", "b", "c", "d"]
    assert rep.rag_model == "gpt-4.1-1"
    assert rep.stable_anchors == ["a"]


def test_run_self_consistency_rejects_zero_runs():
    with pytest.raises(ValueError):
        run_self_consistency("q", strategy="inline_prompted", n_runs=0)


def test_run_self_consistency_uses_precomputed_retrieval():
    precomputed = RetrievalResult(query="q", mode="sentences")
    rag_binding = SimpleNamespace(model_identity="gpt-4.1-1", deployment="gpt-4.1-1")

    with patch(
        "sentcite.self_consistency.get_binding", return_value=rag_binding
    ), patch(
        "sentcite.self_consistency.get_client", return_value=MagicMock()
    ), patch(
        "sentcite.self_consistency.retrieve"
    ) as mock_ret, patch(
        "sentcite.self_consistency.generate"
    ), patch(
        "sentcite.self_consistency.cite_answer",
        side_effect=[_cited([["a"]])] * 2,
    ):
        rep = run_self_consistency(
            "q",
            strategy="post_gen_alignment",
            n_runs=2,
            retrieval=precomputed,
        )

    assert mock_ret.call_count == 0  # never called — we supplied retrieval
    assert rep.retrieval_mode == "sentences"


# ---------------------------------------------------------------------------
# Batch + persistence
# ---------------------------------------------------------------------------


def test_run_self_consistency_batch_and_summary():
    rag_binding = SimpleNamespace(model_identity="gpt-4.1-1", deployment="gpt-4.1-1")
    # 2 questions × 2 runs each, alternating citation sets.
    cite_returns = [
        _cited([["a"]]),  # q1 run 0
        _cited([["a"]]),  # q1 run 1  → q1 stable
        _cited([["b"]]),  # q2 run 0
        _cited([["c"]]),  # q2 run 1  → q2 drifts
    ]
    with patch(
        "sentcite.self_consistency.get_binding", return_value=rag_binding
    ), patch(
        "sentcite.self_consistency.get_client", return_value=MagicMock()
    ), patch(
        "sentcite.self_consistency.retrieve", return_value=_empty_result()
    ), patch(
        "sentcite.self_consistency.generate"
    ), patch(
        "sentcite.self_consistency.cite_answer", side_effect=cite_returns
    ):
        batch = run_self_consistency_batch(
            ["q1", "q2"],
            strategy="inline_prompted",
            n_runs=2,
            temperature=0.5,
        )

    assert len(batch.reports) == 2
    assert batch.reports[0].stability == 1.0
    assert batch.reports[1].stability == 0.0
    summary = batch.to_summary()
    assert summary["items"] == 2
    assert summary["mean_stability"] == 0.5
    assert summary["temperature"] == 0.5


def test_write_stability_batch_round_trip(tmp_path: Path):
    rag_binding = SimpleNamespace(model_identity="gpt-4.1-1", deployment="gpt-4.1-1")
    with patch(
        "sentcite.self_consistency.get_binding", return_value=rag_binding
    ), patch(
        "sentcite.self_consistency.get_client", return_value=MagicMock()
    ), patch(
        "sentcite.self_consistency.retrieve", return_value=_empty_result()
    ), patch(
        "sentcite.self_consistency.generate"
    ), patch(
        "sentcite.self_consistency.cite_answer",
        side_effect=[_cited([["a"]]), _cited([["a"]])],
    ):
        batch = run_self_consistency_batch(
            ["q1"],
            strategy="inline_prompted",
            n_runs=2,
        )

    paths = write_stability_batch(batch, out_dir=tmp_path, run_id="test-run")
    assert paths["reports"].exists()
    assert paths["manifest"].exists()

    lines = paths["reports"].read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["stability"] == 1.0
    assert row["n_runs"] == 2

    manifest = json.loads(paths["manifest"].read_text())
    assert manifest["run_id"] == "test-run"
    assert manifest["items"] == 1
    assert manifest["mean_stability"] == 1.0
