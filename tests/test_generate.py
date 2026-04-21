"""Tests for sentcite.generate — structural, no live LLM calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sentcite.generate import (
    GenerateOutput,
    SYSTEM_A,
    SYSTEM_B,
    build_context_block,
    generate,
)
from sentcite.retrieval import ChunkHit, RetrievalResult, SentenceHit


def _cfg():
    from sentcite.config import AzureConfig

    return AzureConfig(
        storage_account="s", storage_container_raw="r", storage_container_parsed="p",
        storage_connection_string="",
        docintel_endpoint="", docintel_key="",
        search_endpoint="https://s.example.net", search_api_key="",
        search_index_chunks="chunks", search_index_sentences="sentences",
        foundry_name="acct", foundry_endpoint="https://f.services.ai.azure.com",
        foundry_api_key="", foundry_project_name="",
        foundry_project_endpoint="",
        openai_api_version="", openai_chat_deployment="gpt-4.1-1",
        openai_embedding_deployment="text-embedding-3-large",
        synth_gt_endpoint="https://synth.services.ai.azure.com", synth_gt_api_key="",
        synth_gt_deployment="", synth_gt_model="mistral-large",
        judge_endpoint="https://judge.services.ai.azure.com", judge_api_key="",
        judge_deployment="", judge_model="llama-3.3-70b-instruct",
    )


def _result(strategy_data: str = "dual") -> RetrievalResult:
    chunks = [
        ChunkHit(
            chunk_id="doc1-c0000",
            document_id="doc1",
            page=20,
            section_path=["Pub 463", "Standard Mileage Rate"],
            text="For 2025 the rate is 70 cents. You can use it or actual.",
            token_count=14,
            sentences=[
                {"sentence_id": "doc1-s00100", "text": "For 2025 the rate is 70 cents.",
                 "page": 20, "section_path": ["Pub 463", "Standard Mileage Rate"]},
                {"sentence_id": "doc1-s00101", "text": "You can use it or actual.",
                 "page": 20, "section_path": ["Pub 463", "Standard Mileage Rate"]},
            ],
            source="chunk_search",
            score=0.9,
            reranker=3.5,
        ),
        ChunkHit(
            chunk_id="doc1-c0001",
            document_id="doc1",
            page=21,
            section_path=["Pub 463", "Standard Mileage Rate"],
            text="Limitations apply to the standard mileage rate.",
            token_count=7,
            sentences=[
                {"sentence_id": "doc1-s00110", "text": "Limitations apply to the standard mileage rate.",
                 "page": 21, "section_path": ["Pub 463", "Standard Mileage Rate"]},
            ],
            source="sentence_parent",
            score=None,
            reranker=None,
        ),
    ]
    sents = [
        SentenceHit(
            sentence_id="doc1-s00100", chunk_id="doc1-c0000", document_id="doc1",
            page=20, section_path=["Pub 463", "Standard Mileage Rate"],
            text="For 2025 the rate is 70 cents.", reranker=3.5,
        ),
        SentenceHit(
            sentence_id="doc1-s00110", chunk_id="doc1-c0001", document_id="doc1",
            page=21, section_path=["Pub 463", "Standard Mileage Rate"],
            text="Limitations apply to the standard mileage rate.", reranker=3.0,
        ),
    ]
    return RetrievalResult(query="q", mode=strategy_data, chunks=chunks, sentence_candidates=sents)


def test_build_context_block_inline_labels_each_sentence():
    ctx, ids = build_context_block(_result(), include_sentence_ids=True)
    assert "[s:doc1-s00100]" in ctx
    assert "[s:doc1-s00101]" in ctx
    assert "[s:doc1-s00110]" in ctx
    assert "[Chunk 1: doc1-c0000" in ctx
    assert "Pub 463 > Standard Mileage Rate" in ctx
    # Order matches order of appearance in chunks.
    assert ids == ["doc1-s00100", "doc1-s00101", "doc1-s00110"]


def test_build_context_block_plain_text_when_ids_off():
    ctx, ids = build_context_block(_result(), include_sentence_ids=False)
    assert "[s:" not in ctx
    assert ids == []
    assert "For 2025 the rate is 70 cents" in ctx


def test_build_context_block_handles_empty_sentences_gracefully():
    res = _result()
    res.chunks[0].sentences = []
    ctx, ids = build_context_block(res, include_sentence_ids=True)
    # Falls back to chunk body text when there are no labeled sentences.
    assert "For 2025 the rate is 70 cents" in ctx
    # IDs list contains only ids from chunks that still had sentences.
    assert ids == ["doc1-s00110"]


def _fake_response(text: str, *, prompt_tokens=100, completion_tokens=50, finish="stop"):
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish
    resp = MagicMock()
    resp.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    resp.usage = usage
    return resp


def _patched_binding():
    binding = MagicMock()
    binding.deployment = "gpt-4.1-1"
    binding.model_identity = "gpt-4.1-1"
    return binding


def test_generate_strategy_a_uses_system_a_and_labeled_context():
    cfg = _cfg()
    fake_client = MagicMock()
    fake_client.complete.return_value = _fake_response(
        "The rate is 70 cents per mile. [s:doc1-s00100]"
    )
    with patch("sentcite.generate.get_binding", return_value=_patched_binding()), \
         patch("sentcite.generate.get_client", return_value=fake_client):
        out = generate("rate?", _result(), strategy="inline_prompted", cfg=cfg)

    assert isinstance(out, GenerateOutput)
    assert out.strategy == "inline_prompted"
    assert out.model == "gpt-4.1-1"
    assert out.retrieved_chunk_ids == ["doc1-c0000", "doc1-c0001"]
    assert out.candidate_sentence_ids == ["doc1-s00100", "doc1-s00110"]
    assert out.context_sentence_ids == ["doc1-s00100", "doc1-s00101", "doc1-s00110"]
    assert "[s:doc1-s00100]" in out.answer_text
    # System prompt + labeled user prompt.
    call_kwargs = fake_client.complete.call_args.kwargs
    msgs = call_kwargs["messages"]
    assert msgs[0].content == SYSTEM_A
    assert "[s:doc1-s00100]" in msgs[1].content
    assert "Question: rate?" in msgs[1].content
    assert call_kwargs["temperature"] == 0.0


def test_generate_strategy_b_uses_system_b_and_unlabeled_context():
    cfg = _cfg()
    fake_client = MagicMock()
    fake_client.complete.return_value = _fake_response(
        "The 2025 standard mileage rate is 70 cents per mile."
    )
    with patch("sentcite.generate.get_binding", return_value=_patched_binding()), \
         patch("sentcite.generate.get_client", return_value=fake_client):
        out = generate("rate?", _result(), strategy="post_gen_alignment", cfg=cfg)

    assert out.strategy == "post_gen_alignment"
    assert out.context_sentence_ids == []  # no labeling for B
    msgs = fake_client.complete.call_args.kwargs["messages"]
    assert msgs[0].content == SYSTEM_B
    assert "[s:" not in msgs[1].content
    # Layout Y candidate whitelist still propagated for downstream alignment.
    assert out.candidate_sentence_ids == ["doc1-s00100", "doc1-s00110"]
