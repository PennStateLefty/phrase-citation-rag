"""Hybrid retrieval wrapper (Phase 1a baseline).

Implements the dual-layout strategy decided in
``docs/index_projections_eval.md``:

* **Layout Y** (``tax-sentences``) provides the sentence-level citation
  candidate pool: hybrid BM25 + vector, semantic reranked, top-``k_s``.
* **Layout X** (``tax-chunks``) provides the generator's context: top-
  ``k_c`` chunks from hybrid+semantic on the chunk index, **unioned**
  with the parent chunks of the sentence candidates so every citation
  target has its full chunk in the context window.

Single :func:`retrieve` entry point returns a :class:`RetrievalResult`
carrying both populations so downstream code (generator and citation
aligner) can consume each independently.

A ``mode`` flag supports A/B evaluation:

* ``"dual"``       — default; both layouts (production behaviour).
* ``"chunks"``     — Layout X only (context + nested sentences as
  candidates); baseline for ablation.
* ``"sentences"``  — Layout Y only (no chunk context; every hit is a
  standalone sentence); used for ceiling/floor measurements.

Auth: Entra ID via :class:`DefaultAzureCredential` (same singleton as
``sentcite.indexing``). No API keys.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from .config import AzureConfig
from .indexing import _credential, embed_texts

Mode = Literal["dual", "chunks", "sentences"]

_CHUNK_SELECT = [
    "chunk_id", "document_id", "page", "section_path",
    "text", "token_count", "sentences",
]
_SENT_SELECT = [
    "sentence_id", "chunk_id", "document_id", "page",
    "section_path", "text",
]


# ---------------------------------------------------------------------------
# Result dataclasses (lightweight; schema.RetrievedChunk is a different
# pydantic wrapper used elsewhere — intentionally not reused here since
# we carry search-only fields like reranker scores and the hit source).
# ---------------------------------------------------------------------------


@dataclass
class SentenceHit:
    sentence_id: str
    chunk_id: str
    document_id: str
    page: int
    section_path: list[str]
    text: str
    score: float | None = None
    reranker: float | None = None

    @classmethod
    def from_search_doc(cls, d: dict) -> "SentenceHit":
        return cls(
            sentence_id=d["sentence_id"],
            chunk_id=d["chunk_id"],
            document_id=d["document_id"],
            page=int(d.get("page") or 0),
            section_path=list(d.get("section_path") or []),
            text=d.get("text") or "",
            score=d.get("@search.score"),
            reranker=d.get("@search.reranker_score"),
        )


@dataclass
class ChunkHit:
    chunk_id: str
    document_id: str
    page: int
    section_path: list[str]
    text: str
    token_count: int
    sentences: list[dict]
    source: str  # "chunk_search" | "sentence_parent" | "both"
    score: float | None = None
    reranker: float | None = None

    @classmethod
    def from_search_doc(cls, d: dict, *, source: str) -> "ChunkHit":
        return cls(
            chunk_id=d["chunk_id"],
            document_id=d["document_id"],
            page=int(d.get("page") or 0),
            section_path=list(d.get("section_path") or []),
            text=d.get("text") or "",
            token_count=int(d.get("token_count") or 0),
            sentences=list(d.get("sentences") or []),
            source=source,
            score=d.get("@search.score"),
            reranker=d.get("@search.reranker_score"),
        )


@dataclass
class RetrievalResult:
    query: str
    mode: Mode
    chunks: list[ChunkHit] = field(default_factory=list)
    sentence_candidates: list[SentenceHit] = field(default_factory=list)
    latency_ms: float = 0.0
    chunk_search_hits: int = 0
    sentence_search_hits: int = 0
    parent_chunks_added: int = 0

    def candidate_chunk_ids(self) -> list[str]:
        return [c.chunk_id for c in self.chunks]

    def candidate_sentence_ids(self) -> list[str]:
        return [s.sentence_id for s in self.sentence_candidates]


# ---------------------------------------------------------------------------
# Search client factories (overridable in tests)
# ---------------------------------------------------------------------------


def _chunks_client(cfg: AzureConfig) -> SearchClient:
    return SearchClient(
        endpoint=cfg.search_endpoint,
        index_name=cfg.search_index_chunks,
        credential=_credential(),
    )


def _sentences_client(cfg: AzureConfig) -> SearchClient:
    return SearchClient(
        endpoint=cfg.search_endpoint,
        index_name=cfg.search_index_sentences,
        credential=_credential(),
    )


# ---------------------------------------------------------------------------
# Per-layout search
# ---------------------------------------------------------------------------


def search_chunks(
    query: str,
    vec: list[float],
    *,
    cfg: AzureConfig,
    top_k: int = 5,
    vector_k: int | None = None,
    client: SearchClient | None = None,
) -> list[dict]:
    """Hybrid + semantic search against Layout X (``tax-chunks``)."""
    vector_k = vector_k or max(top_k * 4, 20)
    client = client or _chunks_client(cfg)
    return list(
        client.search(
            search_text=query,
            vector_queries=[
                VectorizedQuery(vector=vec, k_nearest_neighbors=vector_k, fields="chunk_vector")
            ],
            query_type="semantic",
            semantic_configuration_name="default",
            top=top_k,
            select=_CHUNK_SELECT,
        )
    )


def search_sentences(
    query: str,
    vec: list[float],
    *,
    cfg: AzureConfig,
    top_k: int = 20,
    vector_k: int | None = None,
    client: SearchClient | None = None,
) -> list[dict]:
    """Hybrid + semantic search against Layout Y (``tax-sentences``)."""
    vector_k = vector_k or max(top_k * 2, 40)
    client = client or _sentences_client(cfg)
    return list(
        client.search(
            search_text=query,
            vector_queries=[
                VectorizedQuery(vector=vec, k_nearest_neighbors=vector_k, fields="sentence_vector")
            ],
            query_type="semantic",
            semantic_configuration_name="default",
            top=top_k,
            select=_SENT_SELECT,
        )
    )


def fetch_chunks_by_id(
    chunk_ids: list[str],
    *,
    cfg: AzureConfig,
    client: SearchClient | None = None,
) -> dict[str, dict]:
    """Bulk-fetch chunks by ``chunk_id``. Returns ``{chunk_id: doc}``.

    Used to expand sentence-candidate parents back to full chunk context
    when chunk-level search didn't already surface them.
    """
    if not chunk_ids:
        return {}
    client = client or _chunks_client(cfg)
    # search.in wants a single delimited string; use '|' as a separator
    # that can't appear in our chunk_ids (which are [A-Za-z0-9_-]).
    joined = "|".join(chunk_ids)
    filt = f"search.in(chunk_id, '{joined}', '|')"
    results = client.search(
        search_text="*",
        filter=filt,
        select=_CHUNK_SELECT,
        top=len(chunk_ids),
    )
    return {d["chunk_id"]: d for d in results}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def retrieve(
    query: str,
    *,
    cfg: AzureConfig | None = None,
    mode: Mode = "dual",
    k_sentences: int = 20,
    k_chunks: int = 5,
    query_vector: list[float] | None = None,
) -> RetrievalResult:
    """Run retrieval for *query* and return the populated result.

    ``mode="dual"`` runs both searches (Layout Y for citation
    candidates, Layout X for generator context) and unions parent
    chunks of the sentence hits into the chunk context so every
    candidate's full chunk is available to the generator.

    Caller may pre-embed the query (``query_vector``) to avoid the
    embeddings round-trip when running retrieve repeatedly.
    """
    cfg = cfg or AzureConfig.from_env()
    t0 = time.perf_counter()

    vec = query_vector if query_vector is not None else embed_texts([query], cfg=cfg)[0]

    res = RetrievalResult(query=query, mode=mode)

    if mode in ("chunks", "dual"):
        chunk_hits = search_chunks(query, vec, cfg=cfg, top_k=k_chunks)
        res.chunk_search_hits = len(chunk_hits)
        res.chunks = [ChunkHit.from_search_doc(d, source="chunk_search") for d in chunk_hits]

    if mode in ("sentences", "dual"):
        sent_hits = search_sentences(query, vec, cfg=cfg, top_k=k_sentences)
        res.sentence_search_hits = len(sent_hits)
        res.sentence_candidates = [SentenceHit.from_search_doc(d) for d in sent_hits]

    if mode == "dual":
        have = {c.chunk_id for c in res.chunks}
        needed = sorted({s.chunk_id for s in res.sentence_candidates} - have)
        if needed:
            extras = fetch_chunks_by_id(needed, cfg=cfg)
            for cid in needed:
                if cid in extras:
                    res.chunks.append(ChunkHit.from_search_doc(extras[cid], source="sentence_parent"))
            res.parent_chunks_added = len(extras)
        sent_parents = {s.chunk_id for s in res.sentence_candidates}
        for c in res.chunks:
            if c.source == "chunk_search" and c.chunk_id in sent_parents:
                c.source = "both"

    if mode == "chunks":
        # Expose nested sentences as citation candidates for parity with
        # dual/sentences modes (ablation baseline).
        for c in res.chunks:
            for s in c.sentences:
                res.sentence_candidates.append(
                    SentenceHit(
                        sentence_id=s["sentence_id"],
                        chunk_id=c.chunk_id,
                        document_id=c.document_id,
                        page=int(s.get("page") or c.page or 0),
                        section_path=list(s.get("section_path") or c.section_path),
                        text=s.get("text") or "",
                    )
                )

    res.latency_ms = (time.perf_counter() - t0) * 1000
    return res
