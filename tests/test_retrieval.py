"""Tests for sentcite.retrieval — structural, no Azure calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sentcite.retrieval import (
    ChunkHit,
    RetrievalResult,
    SentenceHit,
    retrieve,
)


def _cfg():
    from sentcite.config import AzureConfig

    return AzureConfig(
        storage_account="s", storage_container_raw="r", storage_container_parsed="p",
        storage_connection_string="",
        docintel_endpoint="", docintel_key="",
        search_endpoint="https://search.example.net",
        search_api_key="",
        search_index_chunks="chunks",
        search_index_sentences="sentences",
        foundry_name="", foundry_endpoint="https://foundry.example.com",
        foundry_api_key="", foundry_project_name="",
        foundry_project_endpoint="",
        openai_api_version="", openai_chat_deployment="gpt-4.1",
        openai_embedding_deployment="text-embedding-3-large",
        synth_gt_endpoint="https://synth", synth_gt_api_key="",
        synth_gt_deployment="", synth_gt_model="mistral",
        judge_endpoint="https://judge", judge_api_key="",
        judge_deployment="", judge_model="llama",
    )


def _chunk_doc(chunk_id: str, doc_id: str = "doc1", sentences: list[dict] | None = None) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": doc_id,
        "page": 1,
        "section_path": ["T", "H"],
        "text": f"Body of {chunk_id}.",
        "token_count": 5,
        "sentences": sentences or [],
        "@search.score": 0.5,
        "@search.reranker_score": 2.5,
    }


def _sent_doc(sid: str, chunk_id: str, doc_id: str = "doc1") -> dict:
    return {
        "sentence_id": sid,
        "chunk_id": chunk_id,
        "document_id": doc_id,
        "page": 1,
        "section_path": ["T", "H"],
        "text": f"Text of {sid}.",
        "@search.score": 0.6,
        "@search.reranker_score": 3.0,
    }


def test_chunkhit_from_search_doc_captures_scores():
    hit = ChunkHit.from_search_doc(_chunk_doc("doc1-c0000"), source="chunk_search")
    assert hit.chunk_id == "doc1-c0000"
    assert hit.source == "chunk_search"
    assert hit.reranker == 2.5


def test_sentencehit_from_search_doc_captures_scores():
    hit = SentenceHit.from_search_doc(_sent_doc("doc1-s00001", "doc1-c0000"))
    assert hit.sentence_id == "doc1-s00001"
    assert hit.chunk_id == "doc1-c0000"
    assert hit.reranker == 3.0


def test_retrieve_dual_unions_parent_chunks():
    cfg = _cfg()
    # Chunk search returns c0000 only; sentence search returns sentences
    # parented by c0000 AND c0099 → c0099 must be fetched and unioned.
    chunk_hits = [_chunk_doc("doc1-c0000")]
    sent_hits = [
        _sent_doc("doc1-s00001", "doc1-c0000"),
        _sent_doc("doc1-s00099", "doc1-c0099"),
    ]
    extras = {"doc1-c0099": _chunk_doc("doc1-c0099")}

    with patch("sentcite.retrieval.embed_texts", return_value=[[0.0] * 8]), \
         patch("sentcite.retrieval.search_chunks", return_value=chunk_hits), \
         patch("sentcite.retrieval.search_sentences", return_value=sent_hits), \
         patch("sentcite.retrieval.fetch_chunks_by_id", return_value=extras) as fx:
        res = retrieve("q", cfg=cfg, mode="dual", k_sentences=5, k_chunks=3)

    assert isinstance(res, RetrievalResult)
    assert res.mode == "dual"
    assert res.chunk_search_hits == 1
    assert res.sentence_search_hits == 2
    assert res.parent_chunks_added == 1
    ids = {c.chunk_id for c in res.chunks}
    assert ids == {"doc1-c0000", "doc1-c0099"}
    # c0000 was in both populations → marked as "both".
    sources = {c.chunk_id: c.source for c in res.chunks}
    assert sources["doc1-c0000"] == "both"
    assert sources["doc1-c0099"] == "sentence_parent"
    # Only the missing id is fetched.
    fx.assert_called_once()
    args, kwargs = fx.call_args
    requested = args[0] if args else kwargs.get("chunk_ids") or kwargs.get("ids")
    assert requested == ["doc1-c0099"]


def test_retrieve_dual_skips_fetch_when_all_parents_covered():
    cfg = _cfg()
    chunk_hits = [_chunk_doc("doc1-c0000"), _chunk_doc("doc1-c0001")]
    sent_hits = [_sent_doc("doc1-s00001", "doc1-c0000")]

    with patch("sentcite.retrieval.embed_texts", return_value=[[0.0] * 8]), \
         patch("sentcite.retrieval.search_chunks", return_value=chunk_hits), \
         patch("sentcite.retrieval.search_sentences", return_value=sent_hits), \
         patch("sentcite.retrieval.fetch_chunks_by_id") as fx:
        res = retrieve("q", cfg=cfg, mode="dual")

    fx.assert_not_called()
    assert res.parent_chunks_added == 0
    # c0000 appears in both populations; c0001 only in chunk search.
    sources = {c.chunk_id: c.source for c in res.chunks}
    assert sources["doc1-c0000"] == "both"
    assert sources["doc1-c0001"] == "chunk_search"


def test_retrieve_chunks_mode_exposes_nested_sentences_as_candidates():
    cfg = _cfg()
    nested = [
        {"sentence_id": "doc1-s00000", "text": "A.", "page": 1, "section_path": ["T", "H"]},
        {"sentence_id": "doc1-s00001", "text": "B.", "page": 1, "section_path": ["T", "H"]},
    ]
    chunk_hits = [_chunk_doc("doc1-c0000", sentences=nested)]

    with patch("sentcite.retrieval.embed_texts", return_value=[[0.0] * 8]), \
         patch("sentcite.retrieval.search_chunks", return_value=chunk_hits), \
         patch("sentcite.retrieval.search_sentences") as sy, \
         patch("sentcite.retrieval.fetch_chunks_by_id") as fx:
        res = retrieve("q", cfg=cfg, mode="chunks")

    sy.assert_not_called()
    fx.assert_not_called()
    assert [c.chunk_id for c in res.chunks] == ["doc1-c0000"]
    assert {s.sentence_id for s in res.sentence_candidates} == {"doc1-s00000", "doc1-s00001"}
    # Nested candidates inherit the chunk's chunk_id.
    assert all(s.chunk_id == "doc1-c0000" for s in res.sentence_candidates)


def test_retrieve_sentences_mode_skips_chunk_search():
    cfg = _cfg()
    sent_hits = [_sent_doc("doc1-s00001", "doc1-c0000")]
    with patch("sentcite.retrieval.embed_texts", return_value=[[0.0] * 8]), \
         patch("sentcite.retrieval.search_chunks") as sx, \
         patch("sentcite.retrieval.search_sentences", return_value=sent_hits), \
         patch("sentcite.retrieval.fetch_chunks_by_id") as fx:
        res = retrieve("q", cfg=cfg, mode="sentences")

    sx.assert_not_called()
    fx.assert_not_called()
    assert res.chunks == []
    assert [s.sentence_id for s in res.sentence_candidates] == ["doc1-s00001"]


def test_retrieve_accepts_precomputed_query_vector():
    cfg = _cfg()
    with patch("sentcite.retrieval.embed_texts") as emb, \
         patch("sentcite.retrieval.search_chunks", return_value=[]), \
         patch("sentcite.retrieval.search_sentences", return_value=[]):
        retrieve("q", cfg=cfg, mode="dual", query_vector=[0.1] * 8)
    emb.assert_not_called()
