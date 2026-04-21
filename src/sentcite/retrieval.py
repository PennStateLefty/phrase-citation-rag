"""Hybrid retrieval wrapper (BM25 + vector + semantic reranker)."""

from __future__ import annotations

from .schema import RetrievedChunk


def retrieve(query: str, *, top_k: int = 20, rerank_top: int = 5) -> list[RetrievedChunk]:
    raise NotImplementedError
