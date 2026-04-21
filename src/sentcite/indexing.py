"""Azure AI Search index schemas + uploaders.

Two layouts are defined so the `index-projections-spike` todo can evaluate
them head-to-head:

- Layout X: single `chunks` index carrying sentence arrays
  (sentence_ids, sentence_texts, sentence_offsets).
- Layout Y: `chunks` index + child `sentences` index populated via
  Azure AI Search index projections (skillset-driven).

Implementation pending.
"""

from __future__ import annotations

from .schema import Chunk


def ensure_chunk_index(*, include_sentence_arrays: bool) -> None:
    """Create or update the chunks index (Layout X adds sentence arrays)."""
    raise NotImplementedError


def ensure_sentence_index() -> None:
    """Create or update the projected `sentences` child index (Layout Y)."""
    raise NotImplementedError


def upload_chunks(chunks: list[Chunk], *, layout: str) -> None:
    """Embed and upsert chunks (and sentences if layout='Y')."""
    raise NotImplementedError
