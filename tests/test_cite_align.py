"""Tests for sentcite.cite_align — structural, no live LLM/Azure calls."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from sentcite.cite_align import (
    _strip_tags_with_positions,
    align_post_generation,
    cite_answer,
    parse_inline_citations,
)
from sentcite.generate import GenerateOutput
from sentcite.retrieval import ChunkHit, RetrievalResult, SentenceHit


def _result_two_chunks() -> RetrievalResult:
    c0 = ChunkHit(
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
    )
    c1 = ChunkHit(
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
    )
    sents = [
        SentenceHit(
            sentence_id="doc1-s00100", chunk_id="doc1-c0000", document_id="doc1",
            page=20, section_path=["Pub 463", "Standard Mileage Rate"],
            text="For 2025 the rate is 70 cents.",
        ),
        SentenceHit(
            sentence_id="doc1-s00110", chunk_id="doc1-c0001", document_id="doc1",
            page=21, section_path=["Pub 463", "Standard Mileage Rate"],
            text="Limitations apply to the standard mileage rate.",
        ),
    ]
    return RetrievalResult(query="q", mode="dual", chunks=[c0, c1], sentence_candidates=sents)


def _gen(
    answer: str,
    *,
    strategy: str,
    context_ids: list[str] | None = None,
    candidate_ids: list[str] | None = None,
) -> GenerateOutput:
    return GenerateOutput(
        question="rate?",
        strategy=strategy,  # type: ignore[arg-type]
        answer_text=answer,
        model="gpt-4.1-1",
        retrieved_chunk_ids=["doc1-c0000", "doc1-c0001"],
        context_sentence_ids=context_ids or [],
        candidate_sentence_ids=candidate_ids or [],
    )


# ---------------------------------------------------------------------------
# tag stripper
# ---------------------------------------------------------------------------


def test_strip_tags_with_positions_handles_back_to_back_tags():
    text = "Rate is 70 cents.[s:id1][s:id2] And limits apply.[s:id3]"
    clean, anchors = _strip_tags_with_positions(text)
    assert clean == "Rate is 70 cents. And limits apply."
    # Two tags share a position; last tag lands at end of stripped text.
    positions = [p for p, _ in anchors]
    ids = [i for _, i in anchors]
    assert ids == ["id1", "id2", "id3"]
    # Tag positions are idempotent under the clean text indexing.
    assert positions[0] == positions[1]  # back-to-back
    assert positions[2] == len(clean)


def test_strip_tags_handles_no_tags():
    text = "No citations here at all."
    clean, anchors = _strip_tags_with_positions(text)
    assert clean == text
    assert anchors == []


# ---------------------------------------------------------------------------
# Strategy A parser
# ---------------------------------------------------------------------------


def test_parse_inline_citations_attributes_tags_to_correct_sentence():
    answer = (
        "The 2025 rate is 70 cents.[s:doc1-s00100] "
        "Limitations also apply.[s:doc1-s00110]"
    )
    gen = _gen(
        answer,
        strategy="inline_prompted",
        context_ids=["doc1-s00100", "doc1-s00101", "doc1-s00110"],
    )
    cited, report = parse_inline_citations(gen, _result_two_chunks())

    assert cited.strategy == "inline_prompted"
    assert cited.model == "gpt-4.1-1"
    assert "[s:" not in cited.answer_text
    assert len(cited.sentences) == 2
    s0, s1 = cited.sentences
    assert [c.sentence_id for c in s0.citations] == ["doc1-s00100"]
    assert s0.citations[0].source == "llm"
    assert s0.citations[0].confidence == 1.0
    assert s0.citations[0].page == 20
    assert [c.sentence_id for c in s1.citations] == ["doc1-s00110"]
    assert s1.citations[0].chunk_id == "doc1-c0001"
    assert report.total_tags == 2
    assert report.valid_tags == 2
    assert report.hallucinated_ids == []


def test_parse_inline_citations_drops_hallucinated_ids_and_dedupes():
    answer = (
        "Rate is 70 cents.[s:doc1-s00100][s:doc1-s00100][s:doc1-sBOGUS] "
        "More info.[s:doc1-sNOTHERE]"
    )
    gen = _gen(
        answer,
        strategy="inline_prompted",
        context_ids=["doc1-s00100", "doc1-s00110"],
    )
    cited, report = parse_inline_citations(gen, _result_two_chunks())

    assert report.total_tags == 4
    assert report.valid_tags == 2  # the two 's00100' occurrences (both valid)
    assert set(report.hallucinated_ids) == {"doc1-sBOGUS", "doc1-sNOTHERE"}
    # Duplicate valid ids collapse to one citation on the target sentence.
    all_cites = [c.sentence_id for s in cited.sentences for c in s.citations]
    assert all_cites == ["doc1-s00100"]


def test_parse_inline_citations_wrong_strategy_raises():
    gen = _gen("x", strategy="post_gen_alignment")
    import pytest
    with pytest.raises(ValueError):
        parse_inline_citations(gen, _result_two_chunks())


# ---------------------------------------------------------------------------
# Strategy B aligner
# ---------------------------------------------------------------------------


def test_align_post_generation_picks_top_k_above_tau():
    # Two answer sentences. Candidate pool has two sentences.
    # Answer sentence 0 should strongly match candidate 0 (identical vec).
    # Answer sentence 1 should strongly match candidate 1.
    res = _result_two_chunks()
    gen = _gen(
        "For 2025 the rate is 70 cents. Limitations apply to the rate.",
        strategy="post_gen_alignment",
    )
    ans_vecs = [[1.0, 0.0], [0.0, 1.0]]
    cand_vecs = [[1.0, 0.0], [0.0, 1.0]]

    cited = align_post_generation(
        gen, res,
        tau=0.5, top_k=3,
        answer_embeddings=ans_vecs,
        candidate_embeddings=cand_vecs,
    )

    assert cited.strategy == "post_gen_alignment"
    assert len(cited.sentences) == 2
    s0, s1 = cited.sentences
    assert [c.sentence_id for c in s0.citations] == ["doc1-s00100"]
    assert s0.citations[0].source == "aligner"
    assert s0.citations[0].confidence == 1.0
    assert [c.sentence_id for c in s1.citations] == ["doc1-s00110"]
    assert s1.citations[0].confidence == 1.0


def test_align_post_generation_respects_tau_threshold():
    res = _result_two_chunks()
    gen = _gen("One answer sentence here.", strategy="post_gen_alignment")
    # Orthogonal vectors -> cosine 0 -> below tau -> zero citations.
    cited = align_post_generation(
        gen, res,
        tau=0.5, top_k=3,
        answer_embeddings=[[1.0, 0.0]],
        candidate_embeddings=[[0.0, 1.0], [0.0, 1.0]],
    )
    assert cited.sentences[0].citations == []


def test_align_post_generation_caps_at_top_k():
    res = _result_two_chunks()
    # Extend candidate pool to 4 identical vectors; top_k=2 should cap.
    res.sentence_candidates.extend([
        SentenceHit(
            sentence_id=f"doc1-s00{i:03d}",
            chunk_id="doc1-c0000", document_id="doc1", page=20,
            section_path=["Pub 463", "Standard Mileage Rate"],
            text=f"cand{i}",
        )
        for i in (200, 201)
    ])
    gen = _gen("Rate answer sentence.", strategy="post_gen_alignment")
    cited = align_post_generation(
        gen, res,
        tau=0.5, top_k=2,
        answer_embeddings=[[1.0, 0.0]],
        candidate_embeddings=[[1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],
    )
    assert len(cited.sentences[0].citations) == 2


def test_align_post_generation_orders_by_similarity_desc():
    res = _result_two_chunks()
    gen = _gen("The answer sentence.", strategy="post_gen_alignment")
    # candidate 1 is a better match than candidate 0.
    cited = align_post_generation(
        gen, res,
        tau=0.1, top_k=2,
        answer_embeddings=[[1.0, 0.0]],
        candidate_embeddings=[[0.2, 0.98], [0.9, 0.1]],
    )
    ids = [c.sentence_id for c in cited.sentences[0].citations]
    assert ids == ["doc1-s00110", "doc1-s00100"]
    confs = [c.confidence for c in cited.sentences[0].citations]
    assert confs[0] > confs[1]


def test_align_post_generation_wrong_strategy_raises():
    gen = _gen("x", strategy="inline_prompted")
    import pytest
    with pytest.raises(ValueError):
        align_post_generation(gen, _result_two_chunks())


# ---------------------------------------------------------------------------
# Unified dispatch
# ---------------------------------------------------------------------------


def test_cite_answer_dispatches_strategy_a():
    gen = _gen(
        "Rate is 70 cents.[s:doc1-s00100]",
        strategy="inline_prompted",
        context_ids=["doc1-s00100"],
    )
    cited = cite_answer(gen, _result_two_chunks())
    assert cited.strategy == "inline_prompted"
    assert [c.sentence_id for c in cited.sentences[0].citations] == ["doc1-s00100"]


def test_cite_answer_dispatches_strategy_b():
    gen = _gen("The 2025 rate is 70 cents.", strategy="post_gen_alignment")
    res = _result_two_chunks()
    # Monkey-patch embed_texts so no Azure call.
    with patch("sentcite.cite_align.embed_texts",
               side_effect=[[[1.0, 0.0]], [[1.0, 0.0], [0.0, 1.0]]]):
        cited = cite_answer(gen, res, tau=0.5, top_k=3)
    assert cited.strategy == "post_gen_alignment"
    assert cited.sentences[0].citations[0].sentence_id == "doc1-s00100"
    assert cited.sentences[0].citations[0].source == "aligner"
