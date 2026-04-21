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

    # OpenAI
    openai_endpoint: str
    openai_api_key: str
    openai_api_version: str
    openai_chat_deployment: str
    openai_embedding_deployment: str

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
            openai_endpoint=_opt("AZURE_OPENAI_ENDPOINT"),
            openai_api_key=_opt("AZURE_OPENAI_API_KEY"),
            openai_api_version=_opt("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            openai_chat_deployment=_opt("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"),
            openai_embedding_deployment=_opt(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"
            ),
        )
