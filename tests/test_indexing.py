"""Tests for sentcite.indexing — structural, no Azure calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sentcite.indexing import (
    EMBEDDING_DIMENSIONS,
    build_chunks_index,
    build_sentences_index,
    chunk_to_search_doc,
    embed_texts,
    upload_chunks,
    upload_sentences,
)
from sentcite.schema import Chunk, Sentence


def _sent(doc_id: str, i: int, text: str, *, chunk_id: str) -> Sentence:
    return Sentence(
        sentence_id=f"{doc_id}-s{i:05d}",
        chunk_id=chunk_id,
        document_id=doc_id,
        text=text,
        page=1,
        section_path=["T", "H"],
        char_start=0,
        char_end=len(text),
    )


def _chunk(doc_id: str, i: int) -> Chunk:
    chunk_id = f"{doc_id}-c{i:04d}"
    sents = [_sent(doc_id, i * 2, "First sentence.", chunk_id=chunk_id),
             _sent(doc_id, i * 2 + 1, "Second sentence.", chunk_id=chunk_id)]
    return Chunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        page=1,
        section_path=["T", "H"],
        text="First sentence. Second sentence.",
        token_count=6,
        sentences=sents,
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


def test_build_chunks_index_has_required_fields():
    idx = build_chunks_index("my-index")
    field_names = {f.name for f in idx.fields}
    assert {"chunk_id", "document_id", "page", "section_path", "text",
            "token_count", "chunk_vector", "sentences"} <= field_names
    # Vector config uses the documented embedding dims.
    vec = next(f for f in idx.fields if f.name == "chunk_vector")
    assert vec.vector_search_dimensions == EMBEDDING_DIMENSIONS


def test_build_chunks_index_has_vector_and_semantic_config():
    idx = build_chunks_index("my-index")
    assert idx.vector_search is not None
    assert idx.semantic_search is not None
    assert idx.semantic_search.configurations[0].name == "default"


def test_build_chunks_index_nested_sentence_fields():
    idx = build_chunks_index("my-index")
    sentences_field = next(f for f in idx.fields if f.name == "sentences")
    nested = {f.name for f in sentences_field.fields}
    assert {"sentence_id", "text", "page", "char_start", "char_end", "section_path"} <= nested


def test_chunk_to_search_doc_round_trips():
    c = _chunk("doc1", 0)
    vec = [0.1] * EMBEDDING_DIMENSIONS
    doc = chunk_to_search_doc(c, vec)
    assert doc["chunk_id"] == c.chunk_id
    assert doc["document_id"] == "doc1"
    assert doc["chunk_vector"] == vec
    assert len(doc["sentences"]) == 2
    assert doc["sentences"][0]["sentence_id"].startswith("doc1-s")


def test_embed_texts_preserves_order_across_batches():
    def fake_embed(*, input, model):  # noqa: A002
        # Simulate out-of-order server response; caller must sort by index.
        data = [MagicMock(index=i, embedding=[float(i)] * 4) for i in range(len(input))]
        data.reverse()
        return MagicMock(data=data)

    fake_client = MagicMock()
    fake_client.embed.side_effect = fake_embed
    cfg = _cfg()
    texts = [f"t{i}" for i in range(7)]
    with patch("sentcite.indexing._embeddings_client", return_value=fake_client):
        vecs = embed_texts(texts, cfg=cfg, batch_size=3, client=fake_client)
    # One vector per input, in input order.
    assert len(vecs) == 7
    # Index 0 of each batch should have value 0.0 (deterministic fake).
    assert vecs[0] == [0.0] * 4
    assert vecs[3] == [0.0] * 4  # first of second batch
    assert vecs[6] == [0.0] * 4  # first of third batch


def test_upload_chunks_batches_and_counts():
    chunks = [_chunk("doc1", i) for i in range(5)]
    fake_search = MagicMock()
    fake_embed = MagicMock()
    cfg = _cfg()

    with patch("sentcite.indexing._embeddings_client", return_value=fake_embed), \
         patch("sentcite.indexing._search_client", return_value=fake_search), \
         patch("sentcite.indexing.embed_texts",
               return_value=[[0.0] * EMBEDDING_DIMENSIONS for _ in chunks]):
        counts = upload_chunks(chunks, cfg=cfg, batch_size=2)

    assert counts == {"chunks": 5, "sentences": 10}
    # 5 chunks, batch_size=2 -> 3 upload_documents calls.
    assert fake_search.upload_documents.call_count == 3


def test_build_sentences_index_schema():
    idx = build_sentences_index("sent-idx")
    names = {f.name for f in idx.fields}
    assert {"sentence_id", "chunk_id", "document_id", "page", "section_path",
            "text", "token_count", "sentence_vector"} <= names
    key = next(f for f in idx.fields if f.name == "sentence_id")
    assert key.key is True
    vec = next(f for f in idx.fields if f.name == "sentence_vector")
    assert vec.vector_search_dimensions == EMBEDDING_DIMENSIONS
    assert idx.vector_search is not None
    assert idx.semantic_search.configurations[0].name == "default"


def test_upload_sentences_dedupes_by_sentence_id():
    # Two chunks share sentence_id 'doc1-s00000' (overlap case); the
    # sentence index should see it only once.
    c1 = _chunk("doc1", 0)
    c2 = Chunk(
        chunk_id="doc1-c0001",
        document_id="doc1",
        page=1,
        section_path=["T", "H"],
        text="First sentence. Third sentence.",
        token_count=6,
        sentences=[
            c1.sentences[0],  # same sentence_id as in c1
            _sent("doc1", 99, "Third sentence.", chunk_id="doc1-c0001"),
        ],
    )
    fake_search = MagicMock()
    cfg = _cfg()
    with patch("sentcite.indexing._sentences_client", return_value=fake_search), \
         patch("sentcite.indexing.embed_texts",
               side_effect=lambda texts, **kw: [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]):
        counts = upload_sentences([c1, c2], cfg=cfg, batch_size=10)
    # c1 has 2 sentences, c2 adds 1 new (the other dedups). Total unique = 3.
    assert counts == {"sentences": 3}
    assert fake_search.upload_documents.call_count == 1
    uploaded = fake_search.upload_documents.call_args.kwargs["documents"]
    assert len(uploaded) == 3
    ids = [d["sentence_id"] for d in uploaded]
    assert len(set(ids)) == 3
    assert all("sentence_vector" in d and len(d["sentence_vector"]) == EMBEDDING_DIMENSIONS
               for d in uploaded)
