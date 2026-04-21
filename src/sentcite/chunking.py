"""Sentence-aware chunker.

Implementation pending (`chunking` todo). The public contract:

- `chunk_document(parsed_doc) -> list[Chunk]` produces 256-512 token chunks
  with 10-20% overlap at sentence boundaries, preserving section breadcrumbs.
- `split_sentences(text)` uses spaCy en_core_web_sm to return char offsets.

Offsets must round-trip: `text[char_start:char_end] == sentence.text`.
"""

from __future__ import annotations

from .schema import Chunk


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """Return (char_start, char_end, sentence_text) tuples."""
    raise NotImplementedError


def chunk_document(parsed_doc: dict) -> list[Chunk]:
    """Chunk a parsed Document Intelligence output into sentence-tagged chunks."""
    raise NotImplementedError
