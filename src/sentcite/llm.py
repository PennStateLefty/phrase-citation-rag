"""LLM client factory for the three-role eval pipeline.

All three roles (RAG generator, synth-GT author, judge) are accessed through
the Azure AI Inference SDK (``azure-ai-inference``). This gives a single
``ChatCompletionsClient`` surface for both Azure OpenAI deployments inside
the Foundry account and Foundry serverless MaaS deployments (Llama,
Mistral, DeepSeek, Phi, Cohere, ...).

Why not the OpenAI Responses API? It's OpenAI-family only; we'd need a
second SDK to reach the non-OpenAI Foundry catalog models needed to
satisfy the three-distinct-families invariant. Standardising on
``azure-ai-inference`` keeps notebooks uniform.

The module enforces two invariants at import-call time:

1. Three distinct model identities across the RAG / synth-GT / judge roles
   (see :func:`AzureConfig.assert_three_distinct_models`).
2. Required endpoint/key/deployment env vars are set for each role before a
   client is returned. Missing roles fail loudly with a helpful message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

from .config import AzureConfig

Role = Literal["rag", "synth_gt", "judge"]


@dataclass(frozen=True)
class RoleBinding:
    role: Role
    endpoint: str
    api_key: str
    deployment: str
    model_identity: str  # for logging / eval provenance


def _rag_binding(cfg: AzureConfig) -> RoleBinding:
    # The RAG generator is the Azure OpenAI deployment on the Foundry
    # account. azure-ai-inference speaks to Azure OpenAI through the
    # account's /openai/deployments/{name} path; ChatCompletionsClient
    # auto-negotiates when given an Azure OpenAI-shaped endpoint.
    if not cfg.foundry_endpoint or not cfg.foundry_api_key:
        raise RuntimeError(
            "RAG role requires AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY."
        )
    if not cfg.openai_chat_deployment:
        raise RuntimeError("RAG role requires AZURE_OPENAI_CHAT_DEPLOYMENT.")
    # Strip trailing slash so we can append the openai deployments path cleanly.
    base = cfg.foundry_endpoint.rstrip("/")
    endpoint = f"{base}/openai/deployments/{cfg.openai_chat_deployment}"
    return RoleBinding(
        role="rag",
        endpoint=endpoint,
        api_key=cfg.foundry_api_key,
        deployment=cfg.openai_chat_deployment,
        model_identity=cfg.openai_chat_deployment.lower(),
    )


def _synth_gt_binding(cfg: AzureConfig) -> RoleBinding:
    if not (cfg.synth_gt_endpoint and cfg.synth_gt_api_key):
        raise RuntimeError(
            "synth_gt role requires FOUNDRY_SYNTH_GT_ENDPOINT and "
            "FOUNDRY_SYNTH_GT_API_KEY. Click-deploy a non-OpenAI-family "
            "chat model (e.g. Llama-3.3-70B-Instruct, Mistral-Large-2411) "
            "into the Foundry project and populate the env vars."
        )
    ident = (cfg.synth_gt_model or cfg.synth_gt_deployment).lower()
    if not ident:
        raise RuntimeError(
            "synth_gt role requires FOUNDRY_SYNTH_GT_MODEL or "
            "FOUNDRY_SYNTH_GT_DEPLOYMENT so model provenance is tracked."
        )
    return RoleBinding(
        role="synth_gt",
        endpoint=cfg.synth_gt_endpoint.rstrip("/"),
        api_key=cfg.synth_gt_api_key,
        deployment=cfg.synth_gt_deployment,
        model_identity=ident,
    )


def _judge_binding(cfg: AzureConfig) -> RoleBinding:
    if not (cfg.judge_endpoint and cfg.judge_api_key):
        raise RuntimeError(
            "judge role requires FOUNDRY_JUDGE_ENDPOINT and "
            "FOUNDRY_JUDGE_API_KEY. Click-deploy a third model family "
            "(e.g. DeepSeek-V3, Phi-4, Mistral-Large-2411) into the "
            "Foundry project and populate the env vars."
        )
    ident = (cfg.judge_model or cfg.judge_deployment).lower()
    if not ident:
        raise RuntimeError(
            "judge role requires FOUNDRY_JUDGE_MODEL or FOUNDRY_JUDGE_DEPLOYMENT."
        )
    return RoleBinding(
        role="judge",
        endpoint=cfg.judge_endpoint.rstrip("/"),
        api_key=cfg.judge_api_key,
        deployment=cfg.judge_deployment,
        model_identity=ident,
    )


_BINDERS = {
    "rag": _rag_binding,
    "synth_gt": _synth_gt_binding,
    "judge": _judge_binding,
}


def get_binding(role: Role, cfg: AzureConfig | None = None) -> RoleBinding:
    """Resolve a role to its endpoint + key + model identity.

    Runs the three-distinct-models invariant on every call so a misconfigured
    .env fails before any LLM call is made.
    """
    cfg = cfg or AzureConfig.from_env()
    cfg.assert_three_distinct_models()
    return _BINDERS[role](cfg)


def get_client(role: Role, cfg: AzureConfig | None = None) -> ChatCompletionsClient:
    """Return a ready-to-use ChatCompletionsClient for the given role.

    Usage::

        from sentcite.llm import get_client, get_model_id
        client = get_client("rag")
        resp = client.complete(model=get_model_id("rag"), messages=[...])

    The ``model`` arg is required by azure-ai-inference for MaaS deployments
    that host multiple models on one endpoint (it's ignored by single-model
    Azure OpenAI deployment endpoints, but always sending it is safe).
    """
    b = get_binding(role, cfg)
    return ChatCompletionsClient(
        endpoint=b.endpoint,
        credential=AzureKeyCredential(b.api_key),
    )


def get_model_id(role: Role, cfg: AzureConfig | None = None) -> str:
    """Return the deployment/model identifier to pass as ``model=`` on a call."""
    b = get_binding(role, cfg)
    # For Azure OpenAI deployment endpoints, azure-ai-inference accepts the
    # deployment name. For MaaS endpoints, the model name is expected.
    return b.deployment or b.model_identity


def describe_roles(cfg: AzureConfig | None = None) -> dict[Role, str]:
    """Return a role -> model-identity map for logging / eval provenance."""
    cfg = cfg or AzureConfig.from_env()
    cfg.assert_three_distinct_models()
    return {r: _BINDERS[r](cfg).model_identity for r in ("rag", "synth_gt", "judge")}
