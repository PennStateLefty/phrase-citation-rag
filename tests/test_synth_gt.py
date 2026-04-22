"""Tests for sentcite.synth_gt — structural, no live LLM calls."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sentcite.schema import GroundTruthItem
from sentcite.synth_gt import (
    SynthGTFailure,
    SynthGTRun,
    _build_item,
    _classify_difficulty,
    _enumerate_spans,
    _parse_model_json,
    _validate_item_fields,
    Span,
    generate_item,
    load_synth_gt_items,
    select_spans,
    write_synth_gt_run,
)


def _mk_chunk(
    doc: str,
    idx: int,
    sentences: list[str],
    *,
    page: int = 1,
    section: list[str] | None = None,
) -> dict:
    return {
        "document_id": doc,
        "chunk_id": f"{doc}-c{idx:04d}",
        "page": page,
        "section_path": section or [],
        "text": " ".join(sentences),
        "token_count": sum(len(s.split()) for s in sentences),
        "sentences": [
            {
                "sentence_id": f"{doc}-s{idx*100+i:05d}",
                "chunk_id": f"{doc}-c{idx:04d}",
                "document_id": doc,
                "text": s,
                "page": page,
                "section_path": section or [],
                "char_start": 0,
                "char_end": len(s),
            }
            for i, s in enumerate(sentences)
        ],
    }


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def test_parse_model_json_plain():
    obj = _parse_model_json('{"question":"q","gold_answer":"a","rationale":"r"}')
    assert obj["question"] == "q"


def test_parse_model_json_strips_fences():
    content = '```json\n{"question":"q","gold_answer":"a","rationale":"r"}\n```'
    obj = _parse_model_json(content)
    assert obj["gold_answer"] == "a"


def test_parse_model_json_extracts_from_prose():
    content = 'Sure! Here is the JSON:\n{"question":"q","gold_answer":"a","rationale":"r"}\nHope that helps.'
    obj = _parse_model_json(content)
    assert obj["question"] == "q"


def test_parse_model_json_empty_raises():
    with pytest.raises(ValueError):
        _parse_model_json("")


def test_parse_model_json_no_object_raises():
    with pytest.raises(ValueError):
        _parse_model_json("just prose, no JSON here at all")


def test_validate_item_fields_rejects_empty():
    with pytest.raises(ValueError):
        _validate_item_fields({"question": "", "gold_answer": "a"})
    with pytest.raises(ValueError):
        _validate_item_fields({"question": "q", "gold_answer": "  "})


# ---------------------------------------------------------------------------
# Span enumeration + selection
# ---------------------------------------------------------------------------


def test_classify_difficulty():
    # single short sentence w/ digit -> easy
    assert _classify_difficulty([{"text": "Rate is 70 cents."}]) == "easy"
    # single long sentence no digit -> medium
    long = "This is " + ("very " * 40) + "long text."
    assert _classify_difficulty([{"text": long}]) == "medium"
    # two sentences -> medium
    assert _classify_difficulty([{"text": "a"}, {"text": "b"}]) == "medium"
    # three -> hard
    assert _classify_difficulty([{"text": "a"}, {"text": "b"}, {"text": "c"}]) == "hard"


def test_enumerate_spans_respects_max_len_and_single_chunk():
    chunk = _mk_chunk("d1", 0, ["A.", "B.", "C.", "D."])
    spans = _enumerate_spans(chunk, max_span_len=3)
    lengths = {len(s.sentence_ids) for s in spans}
    assert lengths == {1, 2, 3}
    # All spans live inside same chunk
    assert {s.chunk_id for s in spans} == {"d1-c0000"}
    # Total = 4 + 3 + 2 = 9
    assert len(spans) == 9


def test_enumerate_spans_skips_empty_sentence_chunks():
    assert _enumerate_spans({"document_id": "d", "chunk_id": "d-c0", "sentences": []}) == []


def test_select_spans_is_deterministic_for_seed():
    chunks = [_mk_chunk("d", i, ["Alpha beta gamma.", "Delta epsilon."]) for i in range(30)]
    a = select_spans(chunks, target_per_difficulty={"easy": 3, "medium": 3, "hard": 3}, seed=42)
    b = select_spans(chunks, target_per_difficulty={"easy": 3, "medium": 3, "hard": 3}, seed=42)
    assert [s.sentence_ids for s in a] == [s.sentence_ids for s in b]


def test_select_spans_respects_difficulty_quotas():
    # 20 chunks w/ 3 sentences each means plenty of hard candidates, but only
    # 1 sentence w/ digit (easy) shows up per chunk.
    chunks = [
        _mk_chunk("d", i, ["Rate 70 cents.", "Body one.", "Body two."]) for i in range(20)
    ]
    picked = select_spans(
        chunks,
        target_per_difficulty={"easy": 5, "medium": 5, "hard": 5},
        max_spans_per_chunk=1,
        seed=7,
    )
    by_diff = {d: sum(1 for s in picked if s.difficulty == d) for d in ("easy", "medium", "hard")}
    # Quotas capped - never exceed requested counts
    for d in ("easy", "medium", "hard"):
        assert by_diff[d] <= 5
    # At least hard should fill - every chunk has a 3-sentence span
    assert by_diff["hard"] == 5


def test_select_spans_one_per_chunk_cap():
    chunks = [_mk_chunk("d", i, ["Alpha.", "Beta.", "Gamma."]) for i in range(10)]
    picked = select_spans(
        chunks,
        target_per_difficulty={"easy": 20, "medium": 20, "hard": 20},
        max_spans_per_chunk=1,
        seed=1,
    )
    assert len({s.chunk_id for s in picked}) == len(picked)


# ---------------------------------------------------------------------------
# Item construction + generate_item w/ mocked client
# ---------------------------------------------------------------------------


def _span_factory(n_sents: int = 2, difficulty="medium") -> Span:
    return Span(
        document_id="irs_pub_583",
        chunk_id="irs_pub_583-c0042",
        page=3,
        section_path=("Kinds of Records To Keep",),
        sentence_ids=tuple(f"irs_pub_583-s{i:05d}" for i in range(100, 100 + n_sents)),
        text="Keep records of gross receipts. Keep records of expenses.",
        difficulty=difficulty,
    )


def test_build_item_assigns_span_citations_per_answer_sentence():
    span = _span_factory(n_sents=2)
    item = _build_item(
        span=span,
        question="What records must a sole proprietor keep?",
        gold_answer="Keep gross receipts records. Also keep expense records.",
        author_model="mistral-large-3",
        seq=0,
    )
    assert isinstance(item, GroundTruthItem)
    assert item.question_id == "synth-0000-irs_pub_583-c0042"
    assert len(item.gold_citations) >= 1
    # Every answer sentence gets the same span (attribution-first)
    for cites in item.gold_citations:
        assert cites == list(span.sentence_ids)
    assert item.author_model == "mistral-large-3"
    assert item.source_span_sentence_ids == list(span.sentence_ids)
    assert item.document_id == "irs_pub_583"
    assert item.page == 3
    assert item.section_path == ["Kinds of Records To Keep"]


def test_build_item_handles_unsplittable_answer():
    span = _span_factory(n_sents=1)
    item = _build_item(
        span=span,
        question="q?",
        gold_answer="",  # pathological; covered separately by validator, but defensive
        author_model="m",
        seq=3,
    )
    # Even with an empty answer _build_item still produces one row so shape holds.
    assert len(item.gold_citations) >= 1


def _fake_client_returning(content: str):
    client = MagicMock()
    client.complete.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    return client


def test_generate_item_happy_path():
    span = _span_factory()
    client = _fake_client_returning(
        '{"question":"What records must a sole proprietor keep?",'
        '"gold_answer":"Gross receipts. Expense records.",'
        '"rationale":"Both are stated in the span."}'
    )
    item = generate_item(
        span, client=client, model="mistral-large-3",
        author_model="mistral-large-3", seq=1,
    )
    assert item.question.startswith("What records")
    assert item.gold_answer.startswith("Gross receipts")
    assert item.difficulty == "medium"
    # The client was invoked with exactly one call carrying the span text.
    client.complete.assert_called_once()
    kwargs = client.complete.call_args.kwargs
    assert kwargs["model"] == "mistral-large-3"
    assert "DIFFICULTY: medium" in kwargs["messages"][1].content
    assert span.text in kwargs["messages"][1].content


def test_generate_item_raises_on_bad_json():
    span = _span_factory()
    client = _fake_client_returning("not JSON at all")
    with pytest.raises(ValueError):
        generate_item(
            span, client=client, model="m", author_model="m", seq=0,
        )


def test_generate_item_raises_on_missing_fields():
    span = _span_factory()
    client = _fake_client_returning('{"question":"q"}')
    with pytest.raises(ValueError):
        generate_item(
            span, client=client, model="m", author_model="m", seq=0,
        )


# ---------------------------------------------------------------------------
# Run persistence
# ---------------------------------------------------------------------------


def test_write_synth_gt_run_roundtrip(tmp_path: Path):
    span = _span_factory()
    item = _build_item(
        span=span, question="q?", gold_answer="A short answer.",
        author_model="mistral-large-3", seq=0,
    )
    run = SynthGTRun(
        items=[item],
        failures=[
            SynthGTFailure(
                span_chunk_id="irs_pub_583-c9999",
                span_sentence_ids=("irs_pub_583-s99999",),
                difficulty="easy",
                error="ValueError: boom",
            )
        ],
        author_model="mistral-large-3",
        rag_model="gpt-4.1-1",
        judge_model="llama-3.3-70b-instruct",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:05Z",
        seed=7,
        target_counts={"easy": 1},
        elapsed_seconds=5.0,
    )
    paths = write_synth_gt_run(run, out_dir=tmp_path, run_id="testrun")
    assert paths["items"].exists()
    assert paths["failures"].exists()
    assert paths["manifest"].exists()

    manifest = json.loads(paths["manifest"].read_text())
    assert manifest["run_id"] == "testrun"
    assert manifest["total_items"] == 1
    assert manifest["total_failures"] == 1
    assert manifest["author_model"] == "mistral-large-3"
    assert manifest["rag_model"] == "gpt-4.1-1"
    assert manifest["judge_model"] == "llama-3.3-70b-instruct"

    loaded = load_synth_gt_items(paths["items"])
    assert len(loaded) == 1
    assert loaded[0].question_id == item.question_id
    assert loaded[0].source_span_sentence_ids == list(span.sentence_ids)
