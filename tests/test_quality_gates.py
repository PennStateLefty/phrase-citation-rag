"""Tests for sentcite.quality_gates — structural, no live Azure calls."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sentcite.quality_gates import (
    AgreementVerdict,
    QualityGateRun,
    UnionLabelResult,
    _coerce_bool,
    _merge_union_into_item,
    _set_verdict,
    build_sentence_lookup,
    judge_agreement,
    label_union_supports,
    reconstruct_span_text,
    write_quality_gate_run,
)
from sentcite.schema import GroundTruthItem


def _mk_item(**overrides) -> GroundTruthItem:
    base = dict(
        question_id="synth-0000-irs_pub_583-c0042",
        question="What records?",
        difficulty="easy",
        gold_answer="Keep receipts. Keep expenses.",
        gold_citations=[["irs_pub_583-s00100", "irs_pub_583-s00101"]] * 2,
        author_model="mistral-large-3",
        source_span_sentence_ids=["irs_pub_583-s00100", "irs_pub_583-s00101"],
        document_id="irs_pub_583",
        page=3,
        section_path=["Kinds of Records To Keep"],
    )
    base.update(overrides)
    return GroundTruthItem(**base)


def _fake_client_returning(content: str):
    client = MagicMock()
    client.complete.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_coerce_bool_accepts_booleans_and_strings():
    assert _coerce_bool(True, "x") is True
    assert _coerce_bool("false", "x") is False
    assert _coerce_bool("Yes", "x") is True
    assert _coerce_bool("No", "x") is False
    with pytest.raises(ValueError):
        _coerce_bool("maybe", "x")
    with pytest.raises(ValueError):
        _coerce_bool(None, "x")


def test_build_sentence_lookup_flattens_chunks():
    chunks = [
        {"sentences": [{"sentence_id": "a-s0", "text": "alpha"}, {"sentence_id": "a-s1", "text": "beta"}]},
        {"sentences": [{"sentence_id": "b-s0", "text": "gamma"}]},
        {},  # no sentences - should be skipped safely
    ]
    lookup = build_sentence_lookup(chunks)
    assert set(lookup.keys()) == {"a-s0", "a-s1", "b-s0"}
    assert lookup["a-s0"]["text"] == "alpha"


def test_reconstruct_span_text_joins_in_order_and_drops_missing():
    lookup = {"x-s0": {"text": "First."}, "x-s1": {"text": "Second."}}
    assert reconstruct_span_text(["x-s0", "x-s1"], lookup) == "First. Second."
    # Unknown ids are silently dropped.
    assert reconstruct_span_text(["x-s1", "missing"], lookup) == "Second."
    assert reconstruct_span_text([], lookup) == ""


# ---------------------------------------------------------------------------
# Agreement filter
# ---------------------------------------------------------------------------


def test_judge_agreement_parses_pass_verdict():
    item = _mk_item()
    client = _fake_client_returning(
        '{"well_formed": true, "supported": true, "reasons": "matches the span verbatim"}'
    )
    v = judge_agreement(item, "Keep receipts. Keep expenses.", client=client, model="judge-m")
    assert isinstance(v, AgreementVerdict)
    assert v.well_formed and v.supported
    assert "matches" in v.reasons
    # The prompt was called with the span text.
    kwargs = client.complete.call_args.kwargs
    assert kwargs["model"] == "judge-m"
    assert "Keep receipts." in kwargs["messages"][1].content


def test_judge_agreement_parses_fail_verdict_with_fence():
    item = _mk_item()
    content = '```json\n{"well_formed": false, "supported": false, "reasons": "vague"}\n```'
    client = _fake_client_returning(content)
    v = judge_agreement(item, "irrelevant", client=client, model="m")
    assert v.well_formed is False
    assert v.supported is False
    assert v.reasons == "vague"


def test_judge_agreement_raises_on_bad_json():
    item = _mk_item()
    client = _fake_client_returning("I think this is fine, looks good.")
    with pytest.raises(ValueError):
        judge_agreement(item, "span", client=client, model="m")


def test_set_verdict_populates_fields_without_mutating_original():
    item = _mk_item()
    v = AgreementVerdict(well_formed=True, supported=False, reasons="partial")
    reviewed = _set_verdict(item, v, "llama-3.3-70b-instruct")
    assert reviewed.judge_model == "llama-3.3-70b-instruct"
    assert reviewed.judge_well_formed is True
    assert reviewed.judge_supported is False
    assert reviewed.judge_reasons == "partial"
    # Original pydantic model unchanged.
    assert item.judge_model is None


# ---------------------------------------------------------------------------
# Union labeler
# ---------------------------------------------------------------------------


def _cand(sid: str, text: str) -> dict:
    return {
        "sentence_id": sid,
        "chunk_id": sid.rsplit("-s", 1)[0] + "-c0000",
        "document_id": sid.split("-s", 1)[0],
        "page": 1,
        "section_path": [],
        "text": text,
    }


def test_label_union_supports_parses_indices_and_dedupes():
    item = _mk_item()
    pool = [
        _cand("irs_pub_583-s00200", "Also keep expense records."),
        _cand("irs_pub_583-s00201", "Irrelevant sentence about something else."),
        _cand("irs_pub_583-s00202", "Different phrasing: keep receipts."),
    ]
    # duplicate index + out-of-range index: parser should keep unique in-range only.
    content = '{"supporting_indices":[0,2,0,99,-1],"reasons":"entailing claims"}'
    client = _fake_client_returning(content)
    result = label_union_supports(
        item, pool, client=client, model="judge-m", max_candidates=10,
    )
    assert isinstance(result, UnionLabelResult)
    assert result.additions == ["irs_pub_583-s00200", "irs_pub_583-s00202"]
    assert result.considered == 3
    assert result.kept == 2


def test_label_union_supports_handles_empty_pool():
    item = _mk_item()
    client = _fake_client_returning('{"supporting_indices":[]}')
    result = label_union_supports(item, [], client=client, model="m")
    assert result.additions == []
    assert result.considered == 0
    # No LLM call should have been made.
    client.complete.assert_not_called()


def test_label_union_supports_tolerates_bad_json():
    item = _mk_item()
    pool = [_cand("x-s0", "hello")]
    client = _fake_client_returning("not JSON")
    result = label_union_supports(item, pool, client=client, model="m")
    assert result.additions == []
    assert result.kept == 0
    assert "unparseable" in result.reasons


def test_label_union_supports_respects_max_candidates():
    item = _mk_item()
    pool = [_cand(f"x-s{i}", f"t{i}") for i in range(20)]
    client = _fake_client_returning('{"supporting_indices":[]}')
    label_union_supports(item, pool, client=client, model="m", max_candidates=5)
    # Only 5 candidates should appear in the user prompt.
    prompt = client.complete.call_args.kwargs["messages"][1].content
    assert "[0]" in prompt and "[4]" in prompt and "[5]" not in prompt


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def test_merge_union_into_item_adds_per_answer_sentence_and_dedupes():
    item = _mk_item()
    # gold_citations starts as [span, span]
    merged = _merge_union_into_item(item, ["irs_pub_583-s00300", "irs_pub_583-s00100"])
    # s00100 was already in the span - no duplicate.
    for cites in merged.gold_citations:
        assert cites.count("irs_pub_583-s00100") == 1
        assert "irs_pub_583-s00300" in cites
    assert set(merged.union_additions) == {"irs_pub_583-s00300", "irs_pub_583-s00100"}


def test_merge_union_into_item_noop_on_empty_additions():
    item = _mk_item()
    merged = _merge_union_into_item(item, [])
    assert merged is item  # short-circuit returns original


# ---------------------------------------------------------------------------
# Run persistence
# ---------------------------------------------------------------------------


def test_write_quality_gate_run_roundtrip(tmp_path: Path):
    item = _set_verdict(
        _mk_item(),
        AgreementVerdict(well_formed=True, supported=True, reasons="ok"),
        "llama-3.3-70b-instruct",
    )
    run = QualityGateRun(
        items=[item],
        rag_model="gpt-4.1-1",
        synth_model="mistral-large-3",
        judge_model="llama-3.3-70b-instruct",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:05Z",
        elapsed_seconds=5.0,
        agreement_passed=1,
        agreement_failed=0,
        union_additions_total=2,
        failures=[],
    )
    paths = write_quality_gate_run(run, out_dir=tmp_path, run_id="qg-test")
    manifest = json.loads(paths["manifest"].read_text())
    assert manifest["run_id"] == "qg-test"
    assert manifest["agreement_passed"] == 1
    assert manifest["judge_model"] == "llama-3.3-70b-instruct"
    # Reviewed items file is valid jsonl.
    lines = paths["items"].read_text().strip().splitlines()
    assert len(lines) == 1
    loaded = GroundTruthItem.model_validate_json(lines[0])
    assert loaded.judge_well_formed is True
