"""Tests for the three-role LLM factory (no network calls)."""

from __future__ import annotations

import pytest

from sentcite.config import AzureConfig
from sentcite.llm import describe_roles, get_binding


def _cfg(**overrides: str) -> AzureConfig:
    base = dict(
        storage_account="s", storage_container_raw="r", storage_container_parsed="p",
        storage_connection_string="cs",
        docintel_endpoint="https://d", docintel_key="dk",
        search_endpoint="https://s", search_api_key="sk",
        search_index_chunks="c", search_index_sentences="z",
        foundry_name="fn", foundry_endpoint="https://foundry",
        foundry_api_key="fk", foundry_project_name="p",
        foundry_project_endpoint="https://proj",
        openai_api_version="v", openai_chat_deployment="gpt-4o",
        openai_embedding_deployment="emb",
        synth_gt_endpoint="https://synth", synth_gt_api_key="sgk",
        synth_gt_deployment="llama-dep", synth_gt_model="Meta-Llama-3.3-70B-Instruct",
        judge_endpoint="https://judge", judge_api_key="jk",
        judge_deployment="phi-dep", judge_model="Phi-4",
    )
    base.update(overrides)
    return AzureConfig(**base)


def test_three_distinct_models_passes():
    cfg = _cfg()
    cfg.assert_three_distinct_models()  # does not raise


def test_three_distinct_models_rejects_duplicates():
    cfg = _cfg(judge_model="Meta-Llama-3.3-70B-Instruct")
    with pytest.raises(RuntimeError, match="invariant violated"):
        cfg.assert_three_distinct_models()


def test_three_distinct_models_rejects_missing():
    cfg = _cfg(judge_model="", judge_deployment="")
    with pytest.raises(RuntimeError, match="required"):
        cfg.assert_three_distinct_models()


def test_get_binding_rag_shapes_azure_openai_endpoint():
    cfg = _cfg()
    b = get_binding("rag", cfg)
    assert b.endpoint == "https://foundry/openai/deployments/gpt-4o"
    assert b.model_identity == "gpt-4o"
    assert b.deployment == "gpt-4o"


def test_get_binding_synth_gt_and_judge_passthrough():
    cfg = _cfg()
    sg = get_binding("synth_gt", cfg)
    jg = get_binding("judge", cfg)
    assert sg.endpoint == "https://synth"
    assert jg.endpoint == "https://judge"
    assert sg.model_identity == "meta-llama-3.3-70b-instruct"
    assert jg.model_identity == "phi-4"


def test_synth_gt_missing_endpoint_raises():
    cfg = _cfg(synth_gt_endpoint="", synth_gt_api_key="")
    with pytest.raises(RuntimeError, match="synth_gt role requires"):
        get_binding("synth_gt", cfg)


def test_describe_roles_returns_three_distinct_identities():
    cfg = _cfg()
    roles = describe_roles(cfg)
    assert set(roles) == {"rag", "synth_gt", "judge"}
    assert len(set(roles.values())) == 3
