"""Tests for sentcite.chunking — offset round-trip + chunk invariants."""

from __future__ import annotations

import json

import pytest

from sentcite.chunking import (
    chunk_document,
    count_tokens,
    split_sentences,
)


def _layout(paragraphs: list[dict]) -> dict:
    return {"paragraphs": paragraphs, "pages": [{"pageNumber": 1}]}


def _para(content: str, *, role: str | None = None, page: int = 1) -> dict:
    p: dict = {"content": content, "boundingRegions": [{"pageNumber": page}]}
    if role is not None:
        p["role"] = role
    return p


# ----- split_sentences -----


def test_split_sentences_offsets_round_trip():
    text = "First sentence. Second sentence?  Third one!"
    spans = split_sentences(text)
    assert len(spans) == 3
    for start, end, sent_text in spans:
        assert text[start:end] == sent_text


def test_split_sentences_trims_whitespace_but_keeps_round_trip():
    text = "  Leading ws.  Trailing ws.  "
    for start, end, sent_text in split_sentences(text):
        assert sent_text == text[start:end]
        assert sent_text == sent_text.strip()


def test_split_sentences_drops_empty():
    assert split_sentences("") == []
    assert split_sentences("   \n  ") == []


# ----- chunk_document -----


def test_chunk_document_preserves_section_breadcrumbs():
    paragraphs = [
        _para("Main Title", role="title"),
        _para("Section A", role="sectionHeading"),
        _para("Alpha sentence one. Alpha sentence two."),
        _para("Section B", role="sectionHeading"),
        _para("Beta sentence one. Beta sentence two."),
    ]
    chunks = chunk_document("doc1", _layout(paragraphs))
    # Two chunks because section A and B are different.
    assert len(chunks) == 2
    assert chunks[0].section_path == ["Main Title", "Section A"]
    assert chunks[1].section_path == ["Main Title", "Section B"]


def test_chunk_document_offsets_round_trip_within_chunk():
    paragraphs = [
        _para("T", role="title"),
        _para("H", role="sectionHeading"),
        _para("One. Two! Three? Four. Five. Six."),
    ]
    chunks = chunk_document("doc1", _layout(paragraphs))
    for c in chunks:
        for s in c.sentences:
            assert c.text[s.char_start:s.char_end] == s.text


def test_chunk_document_drops_noise_roles():
    paragraphs = [
        _para("Main", role="title"),
        _para("Sec", role="sectionHeading"),
        _para("page 1 of 42", role="pageFooter"),
        _para("Body sentence one. Body sentence two."),
        _para("IRS Publication", role="pageHeader"),
        _para("42", role="pageNumber"),
    ]
    chunks = chunk_document("doc1", _layout(paragraphs))
    joined = " ".join(c.text for c in chunks)
    assert "pageFooter" not in joined
    assert "page 1 of 42" not in joined
    assert "IRS Publication" not in joined
    assert "Body sentence one" in joined


def test_chunk_document_sentence_ids_are_doc_scoped_and_stable():
    paragraphs = [
        _para("T", role="title"),
        _para("H", role="sectionHeading"),
        _para("Alpha one. Beta two. Gamma three. Delta four. Epsilon five."),
    ]
    chunks = chunk_document("doc1", _layout(paragraphs))
    ids = [s.sentence_id for c in chunks for s in c.sentences]
    assert all(i.startswith("doc1-s") for i in ids)
    assert len(set(ids)) == len(ids) == 5


def test_chunk_document_splits_on_target_tokens_with_overlap():
    sentence = "This is a padding sentence used to exceed token thresholds. "
    paragraphs = [
        _para("T", role="title"),
        _para("H", role="sectionHeading"),
        _para(sentence * 200),
    ]
    chunks = chunk_document("doc1", _layout(paragraphs), target_tokens=100, overlap_tokens=20)
    assert len(chunks) >= 2
    # Each chunk stays near target; overlap means the last sentence_id of
    # chunk N reappears as the first sentence_id of chunk N+1.
    first_ids = [c.sentences[0].sentence_id for c in chunks]
    last_ids = [c.sentences[-1].sentence_id for c in chunks]
    overlaps = sum(1 for i in range(len(chunks) - 1) if first_ids[i + 1] <= last_ids[i])
    assert overlaps >= 1


def test_chunk_ids_are_zero_padded_four_digits():
    paragraphs = [
        _para("T", role="title"),
        _para("H", role="sectionHeading"),
        _para("Only sentence here."),
    ]
    chunks = chunk_document("pub17", _layout(paragraphs))
    assert chunks[0].chunk_id == "pub17-c0000"
    assert chunks[0].sentences[0].sentence_id == "pub17-s00000"


def test_count_tokens_nonzero():
    assert count_tokens("Hello, world.") > 0
    assert count_tokens("") == 0
