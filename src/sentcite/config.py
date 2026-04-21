"""Environment-backed configuration (loaded from .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def _opt(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class AzureConfig:
    # Storage
    storage_account: str
    storage_container_raw: str
    storage_container_parsed: str
    storage_connection_string: str

    # Document Intelligence
    docintel_endpoint: str
    docintel_key: str

    # Search
    search_endpoint: str
    search_api_key: str
    search_index_chunks: str
    search_index_sentences: str

    # Foundry / Azure OpenAI (RAG generator role)
    foundry_name: str
    foundry_endpoint: str
    foundry_api_key: str
    foundry_project_name: str
    foundry_project_endpoint: str
    openai_api_version: str
    openai_chat_deployment: str
    openai_embedding_deployment: str

    # Synth-GT author role (non-OpenAI family)
    synth_gt_endpoint: str
    synth_gt_api_key: str
    synth_gt_deployment: str
    synth_gt_model: str

    # Judge role (third distinct model family)
    judge_endpoint: str
    judge_api_key: str
    judge_deployment: str
    judge_model: str

    @classmethod
    def from_env(cls) -> AzureConfig:
        return cls(
            storage_account=_opt("AZURE_STORAGE_ACCOUNT"),
            storage_container_raw=_opt("AZURE_STORAGE_CONTAINER_RAW", "raw-pdfs"),
            storage_container_parsed=_opt("AZURE_STORAGE_CONTAINER_PARSED", "parsed"),
            storage_connection_string=_opt("AZURE_STORAGE_CONNECTION_STRING"),
            docintel_endpoint=_opt("AZURE_DOCINTEL_ENDPOINT"),
            docintel_key=_opt("AZURE_DOCINTEL_KEY"),
            search_endpoint=_opt("AZURE_SEARCH_ENDPOINT"),
            search_api_key=_opt("AZURE_SEARCH_API_KEY"),
            search_index_chunks=_opt("AZURE_SEARCH_INDEX_CHUNKS", "tax-chunks"),
            search_index_sentences=_opt("AZURE_SEARCH_INDEX_SENTENCES", "tax-sentences"),
            foundry_name=_opt("AZURE_FOUNDRY_NAME"),
            foundry_endpoint=_opt("AZURE_FOUNDRY_ENDPOINT"),
            foundry_api_key=_opt("AZURE_FOUNDRY_API_KEY"),
            foundry_project_name=_opt("AZURE_FOUNDRY_PROJECT_NAME", "sentcite"),
            foundry_project_endpoint=_opt("AZURE_FOUNDRY_PROJECT_ENDPOINT"),
            openai_api_version=_opt("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            openai_chat_deployment=_opt("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"),
            openai_embedding_deployment=_opt(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"
            ),
            synth_gt_endpoint=_opt("FOUNDRY_SYNTH_GT_ENDPOINT"),
            synth_gt_api_key=_opt("FOUNDRY_SYNTH_GT_API_KEY"),
            synth_gt_deployment=_opt("FOUNDRY_SYNTH_GT_DEPLOYMENT"),
            synth_gt_model=_opt("FOUNDRY_SYNTH_GT_MODEL"),
            judge_endpoint=_opt("FOUNDRY_JUDGE_ENDPOINT"),
            judge_api_key=_opt("FOUNDRY_JUDGE_API_KEY"),
            judge_deployment=_opt("FOUNDRY_JUDGE_DEPLOYMENT"),
            judge_model=_opt("FOUNDRY_JUDGE_MODEL"),
        )

    def assert_three_distinct_models(self) -> None:
        """Hard rule: RAG generator, synth-GT author, judge must be three
        distinct model identities. Called at the top of synth_gt.py and
        judge.py to prevent same-family contamination of evaluation runs.
        """
        rag = (self.openai_chat_deployment or "").lower()
        synth = (self.synth_gt_model or self.synth_gt_deployment or "").lower()
        judge = (self.judge_model or self.judge_deployment or "").lower()
        if not (rag and synth and judge):
            raise RuntimeError(
                "Three model identities required (RAG, synth-GT, judge); one or more is unset."
            )
        if len({rag, synth, judge}) != 3:
            raise RuntimeError(
                f"Model-identity invariant violated: rag={rag!r}, synth={synth!r}, judge={judge!r} "
                "— all three must be distinct to avoid evaluation contamination."
            )
