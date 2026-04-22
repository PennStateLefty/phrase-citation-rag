"""Tests for sentcite.judge — structural, no live Azure calls."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sentcite.judge import (
    FaithfulnessBatch,
    FaithfulnessReport,
    SentenceFaithfulness,
    _fallback_judgments,
    _format_sources,
    _parse_judge_array,
    build_source_text_lookup,
    judge_faithfulness,
    write_faithfulness_batch,
)
from sentcite.retrieval import ChunkHit, RetrievalResult, SentenceHit
from sentcite.schema import Citation, CitedAnswer, CitedSentence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _cit(sid: str, *, source="llm", conf=1.0) -> Citation:
    return Citation(
        sentence_id=sid,
        chunk_id="irs_pub_463-c0042",
        document_id="irs_pub_463",
        page=20,
        section_path=["Standard Mileage Rate"],
        confidence=conf,
        source=source,
    )


def _cited_answer(sentences: list[CitedSentence]) -> CitedAnswer:
    return CitedAnswer(
        question="What is the 2025 rate?",
        answer_text=" ".join(s.text for s in sentences),
        sentences=sentences,
        strategy="inline_prompted",
        model="gpt-4.1-1",
        retrieved_chunk_ids=["irs_pub_463-c0042"],
    )


def _result_with_source_sentences() -> RetrievalResult:
    chunk = ChunkHit(
        chunk_id="irs_pub_463-c0042",
        document_id="irs_pub_463",
        page=20,
        section_path=["Standard Mileage Rate"],
        text="For 2025 the rate is 70 cents per mile. Limitations apply.",
        token_count=14,
        sentences=[
            {
                "sentence_id": "irs_pub_463-s00100",
                "text": "For 2025 the rate is 70 cents per mile.",
                "chunk_id": "irs_pub_463-c0042",
                "document_id": "irs_pub_463",
                "page": 20,
                "section_path": ["Standard Mileage Rate"],
            },
            {
                "sentence_id": "irs_pub_463-s00101",
                "text": "Limitations apply.",
                "chunk_id": "irs_pub_463-c0042",
                "document_id": "irs_pub_463",
                "page": 20,
                "section_path": ["Standard Mileage Rate"],
            },
        ],
        source="chunk_search",
    )
    cand = SentenceHit(
        sentence_id="irs_pub_17-s99999",
        chunk_id="irs_pub_17-c5000",
        document_id="irs_pub_17",
        page=50,
        section_path=["Car Expenses"],
        text="Taxpayers may use the standard mileage rate in lieu of actual costs.",
    )
    return RetrievalResult(
        query="q", mode="dual", chunks=[chunk], sentence_candidates=[cand]
    )


# ---------------------------------------------------------------------------
# Source lookup
# ---------------------------------------------------------------------------


def test_build_source_text_lookup_merges_chunks_and_candidates():
    result = _result_with_source_sentences()
    lookup = build_source_text_lookup(result)
    assert "irs_pub_463-s00100" in lookup
    assert "irs_pub_463-s00101" in lookup
    assert "irs_pub_17-s99999" in lookup
    assert lookup["irs_pub_463-s00100"]["text"].startswith("For 2025")


def test_format_sources_handles_missing_text():
    # Citation references an id not in the lookup - must still produce a
    # legible line rather than crashing.
    cits = [_cit("doc-sMISSING")]
    out = _format_sources(cits, {})
    assert "[0]" in out
    assert "source text unavailable" in out


# ---------------------------------------------------------------------------
# Judge array parser
# ---------------------------------------------------------------------------


def test_parse_judge_array_direct_array():
    arr = _parse_judge_array(
        '[{"entails":true,"reason":"match"},{"entails":false,"reason":"nope"}]',
        expected=2,
    )
    assert len(arr) == 2
    assert arr[0]["entails"] is True


def test_parse_judge_array_with_fence():
    content = '```json\n[{"entails":true,"reason":"ok"}]\n```'
    arr = _parse_judge_array(content, expected=1)
    assert arr[0]["entails"] is True


def test_parse_judge_array_wrapped_object():
    content = '{"judgments":[{"entails":true,"reason":"ok"}]}'
    arr = _parse_judge_array(content, expected=1)
    assert arr[0]["entails"] is True


def test_parse_judge_array_pads_short_output():
    # Only 1 entry when 3 expected → pad with conservative defaults.
    arr = _parse_judge_array('[{"entails":true,"reason":"ok"}]', expected=3)
    assert len(arr) == 3
    assert arr[0]["entails"] is True
    assert arr[1]["entails"] is False
    assert "fewer entries" in arr[1]["reason"]


def test_parse_judge_array_truncates_long_output():
    arr = _parse_judge_array(
        '[{"entails":true,"reason":"a"},{"entails":true,"reason":"b"},{"entails":true,"reason":"c"}]',
        expected=2,
    )
    assert len(arr) == 2


def test_parse_judge_array_raises_on_malformed_entry():
    with pytest.raises(ValueError):
        _parse_judge_array('[{"no_entails_field":true}]', expected=1)


def test_parse_judge_array_accepts_single_object_for_single_expected():
    arr = _parse_judge_array('{"entails":false,"reason":"weak"}', expected=1)
    assert arr[0]["entails"] is False


# ---------------------------------------------------------------------------
# Fallback judgments
# ---------------------------------------------------------------------------


def test_fallback_judgments_marks_every_citation_unfaithful():
    sent = CitedSentence(
        index=0,
        text="For 2025 the rate is 70 cents per mile.",
        citations=[_cit("x-s0"), _cit("x-s1")],
    )
    js = _fallback_judgments(sent, reason="boom")
    assert len(js) == 2
    assert all(j.entails is False for j in js)
    assert all(j.reason == "boom" for j in js)


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


def test_sentence_faithfulness_aggregate_properties():
    from sentcite.judge import FaithfulnessJudgment

    judgments = [
        FaithfulnessJudgment(0, "t", "a", "c", "llm", 1.0, True, "ok"),
        FaithfulnessJudgment(0, "t", "b", "c", "llm", 1.0, False, "no"),
    ]
    sf = SentenceFaithfulness(index=0, text="t", judgments=judgments)
    assert sf.citation_count == 2
    assert sf.faithful_count == 1
    assert sf.any_faithful is True
    assert sf.all_faithful is False

    empty = SentenceFaithfulness(index=1, text="t", judgments=[])
    assert empty.any_faithful is False
    assert empty.all_faithful is False


def test_faithfulness_report_percent_faithful_and_coverage():
    from sentcite.judge import FaithfulnessJudgment

    s0 = SentenceFaithfulness(
        index=0,
        text="a",
        judgments=[
            FaithfulnessJudgment(0, "a", "x", "c", "llm", 1.0, True, ""),
            FaithfulnessJudgment(0, "a", "y", "c", "llm", 1.0, False, ""),
        ],
    )
    s1 = SentenceFaithfulness(
        index=1,
        text="b",
        judgments=[FaithfulnessJudgment(1, "b", "z", "c", "llm", 1.0, True, "")],
    )
    s2 = SentenceFaithfulness(index=2, text="c", judgments=[])  # uncited
    r = FaithfulnessReport(
        question="q",
        strategy="inline_prompted",
        rag_model="gpt",
        synth_model="mistral",
        judge_model="llama",
        sentences=[s0, s1, s2],
    )
    assert r.total_citations == 3
    assert r.faithful_citations == 2
    assert r.percent_faithful == pytest.approx(66.67, abs=0.01)
    # 2/3 sentences are cited; of those, both have >=1 faithful cite -> 100%.
    assert r.percent_sentences_any_faithful == 100.0
    # 2/3 answer sentences had any citation.
    assert r.coverage == pytest.approx(66.67, abs=0.01)


# ---------------------------------------------------------------------------
# Full judge_faithfulness with mocked bindings + client
# ---------------------------------------------------------------------------


def _mock_bindings():
    """Patch get_binding / get_client / get_model_id for judge_faithfulness."""
    rag = SimpleNamespace(model_identity="gpt-4.1-1", deployment="gpt-4.1-1")
    synth = SimpleNamespace(model_identity="mistral-large-3", deployment="Mistral-large-3")
    judge = SimpleNamespace(
        model_identity="llama-3.3-70b-instruct", deployment="Llama-3.3-70B-Instruct"
    )

    def _get_binding(role, cfg=None):
        return {"rag": rag, "synth_gt": synth, "judge": judge}[role]

    return _get_binding, rag, synth, judge


def _fake_client_with_responses(responses: list[str]):
    """MagicMock that returns responses in order on each .complete() call."""
    client = MagicMock()
    client.complete.side_effect = [
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=r))])
        for r in responses
    ]
    return client


def test_judge_faithfulness_happy_path():
    result = _result_with_source_sentences()
    cited = _cited_answer(
        [
            CitedSentence(
                index=0,
                text="The 2025 rate is 70 cents per mile.",
                citations=[
                    _cit("irs_pub_463-s00100"),
                    _cit("irs_pub_463-s00101"),  # weak match - judge should say false
                ],
            ),
        ]
    )
    responses = [
        '[{"entails":true,"reason":"span states the rate verbatim"},'
        '{"entails":false,"reason":"only mentions limitations"}]',
    ]
    client = _fake_client_with_responses(responses)

    _get_binding, rag, synth, judge = _mock_bindings()
    with patch("sentcite.judge.get_binding", side_effect=_get_binding), \
         patch("sentcite.judge.get_client", return_value=client), \
         patch("sentcite.judge.get_model_id", return_value="Llama-3.3-70B-Instruct"):
        rep = judge_faithfulness(cited, result)

    assert rep.rag_model == "gpt-4.1-1"
    assert rep.judge_model == "llama-3.3-70b-instruct"
    assert rep.total_citations == 2
    assert rep.faithful_citations == 1
    assert rep.percent_faithful == 50.0
    assert rep.sentences[0].any_faithful is True
    assert rep.sentences[0].all_faithful is False


def test_judge_faithfulness_contamination_guard_raises():
    result = _result_with_source_sentences()
    # CitedAnswer authored by the same model identity as the configured judge.
    cited = _cited_answer(
        [CitedSentence(index=0, text="t", citations=[_cit("irs_pub_463-s00100")])]
    )
    cited = cited.model_copy(update={"model": "llama-3.3-70b-instruct"})

    _get_binding, *_ = _mock_bindings()
    with patch("sentcite.judge.get_binding", side_effect=_get_binding), \
         patch("sentcite.judge.get_client", return_value=MagicMock()), \
         patch("sentcite.judge.get_model_id", return_value="Llama-3.3-70B-Instruct"), \
         pytest.raises(RuntimeError, match="contamination guard"):
        judge_faithfulness(cited, result)


def test_judge_faithfulness_skips_uncited_sentences():
    result = _result_with_source_sentences()
    cited = _cited_answer(
        [
            CitedSentence(index=0, text="Uncited sentence.", citations=[]),
            CitedSentence(
                index=1,
                text="Cited sentence.",
                citations=[_cit("irs_pub_463-s00100")],
            ),
        ]
    )
    client = _fake_client_with_responses(['[{"entails":true,"reason":"ok"}]'])

    _get_binding, *_ = _mock_bindings()
    with patch("sentcite.judge.get_binding", side_effect=_get_binding), \
         patch("sentcite.judge.get_client", return_value=client), \
         patch("sentcite.judge.get_model_id", return_value="m"):
        rep = judge_faithfulness(cited, result)

    # Judge called exactly once - uncited sentence skipped.
    assert client.complete.call_count == 1
    assert rep.sentences[0].citation_count == 0
    assert rep.sentences[1].faithful_count == 1


def test_judge_faithfulness_records_error_on_bad_json():
    result = _result_with_source_sentences()
    cited = _cited_answer(
        [CitedSentence(index=0, text="t", citations=[_cit("irs_pub_463-s00100")])]
    )
    client = _fake_client_with_responses(["not a valid JSON response at all"])

    _get_binding, *_ = _mock_bindings()
    with patch("sentcite.judge.get_binding", side_effect=_get_binding), \
         patch("sentcite.judge.get_client", return_value=client), \
         patch("sentcite.judge.get_model_id", return_value="m"):
        rep = judge_faithfulness(cited, result)

    assert len(rep.errors) == 1
    # Fallback marks unfaithful rather than silently dropping the citation.
    assert rep.sentences[0].faithful_count == 0
    assert "parse failed" in rep.sentences[0].judgments[0].reason


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_write_faithfulness_batch_roundtrip(tmp_path: Path):
    from sentcite.judge import FaithfulnessJudgment

    rep = FaithfulnessReport(
        question="q",
        strategy="inline_prompted",
        rag_model="gpt-4.1-1",
        synth_model="mistral-large-3",
        judge_model="llama-3.3-70b-instruct",
        sentences=[
            SentenceFaithfulness(
                index=0,
                text="t",
                judgments=[
                    FaithfulnessJudgment(
                        0, "t", "x-s0", "x-c0", "llm", 1.0, True, "entails"
                    )
                ],
            )
        ],
    )
    batch = FaithfulnessBatch(
        reports=[rep],
        rag_model="gpt-4.1-1",
        synth_model="mistral-large-3",
        judge_model="llama-3.3-70b-instruct",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:05Z",
        elapsed_seconds=5.0,
    )
    paths = write_faithfulness_batch(batch, out_dir=tmp_path, run_id="fj-test")
    assert paths["reports"].exists()
    manifest = json.loads(paths["manifest"].read_text())
    assert manifest["run_id"] == "fj-test"
    assert manifest["total_citations"] == 1
    assert manifest["faithful_citations"] == 1
    assert manifest["percent_faithful"] == 100.0
    # Reports file is valid JSONL.
    lines = paths["reports"].read_text().strip().splitlines()
    obj = json.loads(lines[0])
    assert obj["sentences"][0]["judgments"][0]["entails"] is True
