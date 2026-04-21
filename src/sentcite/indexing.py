"""Azure AI Search index schema + uploader (Layout X baseline).

Baseline index layout:

* One ``chunks`` index with ``chunk_vector`` (3072-d) for hybrid search.
* ``sentences`` is a complex collection nested inside each chunk document,
  carrying per-sentence id/text/page/char offsets/section_path. That gives
  the citation aligner everything it needs without a second index.

Layout Y (projected sentence index) is the next spike; this module stays
focused on X so we can measure first.

Auth: Entra ID via :class:`DefaultAzureCredential` on both the Search
management client and the Search data client, and on the
``azure-ai-inference`` :class:`EmbeddingsClient` that calls
``text-embedding-3-large`` at Foundry.

Required RBAC on the caller:

* ``Search Service Contributor`` on the Search service (create/update index).
* ``Search Index Data Contributor`` on the Search service (upload docs).
* ``Cognitive Services User`` / ``Cognitive Services OpenAI User`` on the
  Foundry account (embeddings call).

The Search service must have AAD auth enabled (``authOptions=aadOrApiKey``);
the defaults produced by the 2025 Bicep template come up as ``apiKeyOnly``
and must be switched with::

    az search service update -g <rg> -n <name> --auth-options aadOrApiKey \
      --aad-auth-failure-mode http403
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from azure.ai.inference import EmbeddingsClient
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    ComplexField,
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmKind,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

from .config import AzureConfig
from .schema import Chunk

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"

EMBEDDING_DIMENSIONS = 3072  # text-embedding-3-large full dimension.
DEFAULT_SEMANTIC_CONFIG_NAME = "default"
DEFAULT_VECTOR_PROFILE_NAME = "chunk-vector-profile"
DEFAULT_HNSW_CONFIG_NAME = "chunk-vector-hnsw"


_CREDENTIAL: TokenCredential | None = None


def _credential() -> TokenCredential:
    global _CREDENTIAL
    if _CREDENTIAL is None:
        _CREDENTIAL = DefaultAzureCredential()
    return _CREDENTIAL


@dataclass(frozen=True)
class IndexNames:
    chunks: str


def index_names(cfg: AzureConfig) -> IndexNames:
    return IndexNames(chunks=cfg.search_index_chunks)


# ---------------------------------------------------------------------------
# Index schema
# ---------------------------------------------------------------------------


def build_chunks_index(name: str, *, dimensions: int = EMBEDDING_DIMENSIONS) -> SearchIndex:
    """Return the Layout X ``chunks`` index definition."""
    fields: list = [
        SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True, facetable=True, sortable=True),
        SimpleField(name="page", type=SearchFieldDataType.Int32, filterable=True, sortable=True, facetable=True),
        SimpleField(
            name="section_path",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
            facetable=True,
        ),
        SearchableField(name="text", type=SearchFieldDataType.String, analyzer_name="en.lucene"),
        SimpleField(name="token_count", type=SearchFieldDataType.Int32, filterable=False, sortable=True),
        SearchField(
            name="chunk_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=dimensions,
            vector_search_profile_name=DEFAULT_VECTOR_PROFILE_NAME,
            hidden=False,
        ),
        ComplexField(
            name="sentences",
            collection=True,
            fields=[
                SimpleField(name="sentence_id", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="text", type=SearchFieldDataType.String, analyzer_name="en.lucene"),
                SimpleField(name="page", type=SearchFieldDataType.Int32, filterable=True),
                SimpleField(name="char_start", type=SearchFieldDataType.Int32),
                SimpleField(name="char_end", type=SearchFieldDataType.Int32),
                SimpleField(
                    name="section_path",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                    filterable=True,
                ),
            ],
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name=DEFAULT_HNSW_CONFIG_NAME,
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters=HnswParameters(
                    m=4, ef_construction=400, ef_search=500,
                    metric=VectorSearchAlgorithmMetric.COSINE,
                ),
            )
        ],
        profiles=[
            VectorSearchProfile(
                name=DEFAULT_VECTOR_PROFILE_NAME,
                algorithm_configuration_name=DEFAULT_HNSW_CONFIG_NAME,
            )
        ],
    )

    semantic = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name=DEFAULT_SEMANTIC_CONFIG_NAME,
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="text")],
                    keywords_fields=[SemanticField(field_name="section_path")],
                ),
            )
        ]
    )

    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic,
    )


def ensure_chunks_index(cfg: AzureConfig | None = None, *, recreate: bool = False) -> str:
    """Create or update the chunks index. Returns the index name.

    ``recreate=True`` drops and recreates (use when fields change).
    """
    cfg = cfg or AzureConfig.from_env()
    if not cfg.search_endpoint:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT is required for indexing.")
    idx_client = SearchIndexClient(endpoint=cfg.search_endpoint, credential=_credential())
    name = cfg.search_index_chunks
    index = build_chunks_index(name)
    if recreate:
        try:
            idx_client.delete_index(name)
        except Exception:  # noqa: BLE001
            pass
    idx_client.create_or_update_index(index)
    return name


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


def _embeddings_client(cfg: AzureConfig) -> EmbeddingsClient:
    if not cfg.foundry_endpoint or not cfg.openai_embedding_deployment:
        raise RuntimeError(
            "AZURE_FOUNDRY_ENDPOINT and AZURE_OPENAI_EMBEDDING_DEPLOYMENT required."
        )
    base = cfg.foundry_endpoint.rstrip("/")
    endpoint = f"{base}/openai/deployments/{cfg.openai_embedding_deployment}"
    return EmbeddingsClient(
        endpoint=endpoint,
        credential=_credential(),
        credential_scopes=[COGNITIVE_SERVICES_SCOPE],
    )


def embed_texts(
    texts: list[str],
    *,
    cfg: AzureConfig | None = None,
    batch_size: int = 64,
    client: EmbeddingsClient | None = None,
) -> list[list[float]]:
    """Return one embedding vector per input, in the same order.

    Batched for throughput; Azure OpenAI ``text-embedding-3-large``
    accepts up to 2048 inputs / 300K tokens per call, but 64 keeps us
    comfortably under any per-request token cap for ~400-token chunks.
    """
    cfg = cfg or AzureConfig.from_env()
    client = client or _embeddings_client(cfg)
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embed(input=batch, model=cfg.openai_embedding_deployment)
        ordered = sorted(resp.data, key=lambda d: d.index)
        out.extend(d.embedding for d in ordered)
    return out


# ---------------------------------------------------------------------------
# Chunk -> Search document
# ---------------------------------------------------------------------------


def chunk_to_search_doc(chunk: Chunk, embedding: list[float]) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "page": chunk.page,
        "section_path": list(chunk.section_path),
        "text": chunk.text,
        "token_count": chunk.token_count,
        "chunk_vector": embedding,
        "sentences": [
            {
                "sentence_id": s.sentence_id,
                "text": s.text,
                "page": s.page,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "section_path": list(s.section_path),
            }
            for s in chunk.sentences
        ],
    }


def _search_client(cfg: AzureConfig) -> SearchClient:
    return SearchClient(
        endpoint=cfg.search_endpoint,
        index_name=cfg.search_index_chunks,
        credential=_credential(),
    )


def upload_chunks(
    chunks: Iterable[Chunk],
    *,
    cfg: AzureConfig | None = None,
    batch_size: int = 100,
    embed_batch_size: int = 64,
) -> dict[str, int]:
    """Embed and upload chunks to the ``chunks`` index. Returns counts."""
    cfg = cfg or AzureConfig.from_env()
    chunks = list(chunks)
    if not chunks:
        return {"chunks": 0, "sentences": 0}
    texts = [c.text for c in chunks]
    vectors = embed_texts(texts, cfg=cfg, batch_size=embed_batch_size)
    if len(vectors) != len(chunks):
        raise RuntimeError(
            f"Embedding count mismatch: got {len(vectors)} vectors for {len(chunks)} chunks."
        )
    client = _search_client(cfg)
    total_sentences = 0
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i : i + batch_size]
        batch_vectors = vectors[i : i + batch_size]
        docs = [chunk_to_search_doc(c, v) for c, v in zip(batch_chunks, batch_vectors)]
        client.upload_documents(documents=docs)
        total_sentences += sum(len(c.sentences) for c in batch_chunks)
    return {"chunks": len(chunks), "sentences": total_sentences}


def load_chunks_from_jsonl(path: Path) -> list[Chunk]:
    out: list[Chunk] = []
    with Path(path).open() as f:
        for line in f:
            if line.strip():
                out.append(Chunk.model_validate_json(line))
    return out
