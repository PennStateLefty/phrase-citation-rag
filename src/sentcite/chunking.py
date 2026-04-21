"""Sentence-aware chunker.

Consumes the ``layout.json`` produced by :mod:`sentcite.ingest` and emits
:class:`~sentcite.schema.Chunk` records whose ``sentences`` carry stable,
document-scoped ``sentence_id``s and char offsets that round-trip against
the chunk's own ``text`` (i.e. ``chunk.text[s.char_start:s.char_end]`` is
exactly ``s.text``).

ID scheme (document-scoped so sentence_ids survive chunk re-splitting):

* ``chunk_id``    ``{document_id}::c{chunk_idx:04d}``
* ``sentence_id`` ``{document_id}::s{global_sent_idx:05d}``

Chunking policy:

* Drop paragraphs with role in ``_NOISE_ROLES`` (pageHeader, pageFooter,
  pageNumber, footnote).
* ``title`` paragraphs set H1 of the section path; ``sectionHeading``
  paragraphs become H2. A deeper hierarchy is not produced by Document
  Intelligence Layout, so two levels is the floor.
* Chunks never cross a section boundary — a heading change forces a new
  chunk. This keeps ``section_path`` meaningful on every retrieved chunk.
* Within a section we greedily pack sentences up to ``target_tokens``
  (default 400, inside the plan's 256-512 band) and then start a new
  chunk carrying a small sentence-boundary ``overlap_tokens`` (default 40,
  ~10%) for retrieval recall. Sentence identities are stable across the
  overlap — the same sentence appears in both chunks with the same
  ``sentence_id`` but different ``chunk_id`` and char offsets.

Tokenizer: ``tiktoken`` ``cl100k_base`` (matches GPT-4o/4.1 and most
embedding models closely enough for chunk sizing).
Sentence splitter: blank spaCy English pipeline + ``sentencizer`` — no
model download, ~rule-based on punctuation + whitespace. Adequate for
prose in IRS publications; revisit if tables/lists produce bad splits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import spacy
import tiktoken

from .schema import Chunk, Sentence

_NOISE_ROLES = {"pageHeader", "pageFooter", "pageNumber", "footnote"}

_nlp = None
_tok_enc = None


def _nlp_singleton():
    global _nlp
    if _nlp is None:
        n = spacy.blank("en")
        n.add_pipe("sentencizer")
        _nlp = n
    return _nlp


def _tok_singleton():
    global _tok_enc
    if _tok_enc is None:
        _tok_enc = tiktoken.get_encoding("cl100k_base")
    return _tok_enc


def count_tokens(text: str) -> int:
    return len(_tok_singleton().encode(text))


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """Return ``(char_start, char_end, sentence_text)`` tuples.

    Offsets round-trip: ``text[char_start:char_end] == sentence_text`` for
    every entry. Leading/trailing whitespace is trimmed out of the span,
    and empty/whitespace-only sentences are dropped.
    """
    if not text:
        return []
    doc = _nlp_singleton()(text)
    out: list[tuple[int, int, str]] = []
    for s in doc.sents:
        start, end = s.start_char, s.end_char
        # Trim whitespace without losing round-trip integrity.
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            out.append((start, end, text[start:end]))
    return out


@dataclass(frozen=True)
class _SentRec:
    idx: int
    text: str
    page: int
    section_path: tuple[str, ...]


def _iter_sentence_records(layout: dict) -> list[_SentRec]:
    """Walk DI paragraphs → linear sentence list with section breadcrumbs."""
    paragraphs = layout.get("paragraphs", [])
    title: str | None = None
    heading: str | None = None
    out: list[_SentRec] = []
    idx = 0
    for p in paragraphs:
        role = p.get("role")
        if role in _NOISE_ROLES:
            continue
        content = (p.get("content") or "").strip()
        if not content:
            continue
        if role == "title":
            # Multi-line titles land as consecutive title paragraphs in DI.
            title = content if title is None else f"{title} — {content}"
            heading = None
            continue
        if role == "sectionHeading":
            heading = content
            continue
        regions = p.get("boundingRegions") or [{}]
        page = int(regions[0].get("pageNumber", 1) or 1)
        section_path = tuple(x for x in (title, heading) if x)
        for _, _, stext in split_sentences(content):
            out.append(_SentRec(idx=idx, text=stext, page=page, section_path=section_path))
            idx += 1
    return out


def _assemble_chunks(
    sents: list[_SentRec],
    *,
    target_tokens: int,
    overlap_tokens: int,
) -> Iterator[list[_SentRec]]:
    """Yield lists of _SentRec, one per chunk.

    A chunk is flushed when (a) the section path changes, or (b) adding
    the next sentence would exceed ``target_tokens``. Same-section flushes
    seed the next chunk with a trailing sentence window up to
    ``overlap_tokens``.
    """
    current: list[_SentRec] = []
    current_key: tuple[str, ...] | None = None
    current_tokens = 0
    for s in sents:
        s_tokens = count_tokens(s.text)
        section_changed = current_key is not None and s.section_path != current_key
        would_overflow = bool(current) and (current_tokens + s_tokens > target_tokens)
        if current and (section_changed or would_overflow):
            yield current
            if section_changed:
                current, current_tokens = [], 0
            else:
                overlap: list[_SentRec] = []
                otok = 0
                for x in reversed(current):
                    t = count_tokens(x.text)
                    if overlap and otok + t > overlap_tokens:
                        break
                    overlap.insert(0, x)
                    otok += t
                    if otok >= overlap_tokens:
                        break
                current = overlap
                current_tokens = otok
        current.append(s)
        current_tokens += s_tokens
        current_key = s.section_path
    if current:
        yield current


def _build_chunk(document_id: str, chunk_idx: int, sents: list[_SentRec]) -> Chunk:
    chunk_id = f"{document_id}::c{chunk_idx:04d}"
    parts: list[str] = []
    sentence_records: list[Sentence] = []
    cursor = 0
    for s in sents:
        if parts:
            parts.append(" ")
            cursor += 1
        start = cursor
        parts.append(s.text)
        cursor += len(s.text)
        sentence_records.append(
            Sentence(
                sentence_id=f"{document_id}::s{s.idx:05d}",
                chunk_id=chunk_id,
                document_id=document_id,
                text=s.text,
                page=s.page,
                section_path=list(s.section_path),
                char_start=start,
                char_end=cursor,
            )
        )
    text = "".join(parts)
    first = sents[0]
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        page=first.page,
        section_path=list(first.section_path),
        text=text,
        token_count=count_tokens(text),
        sentences=sentence_records,
    )


def chunk_document(
    document_id: str,
    layout: dict,
    *,
    target_tokens: int = 400,
    overlap_tokens: int = 40,
) -> list[Chunk]:
    """Chunk a Document Intelligence AnalyzeResult into sentence-tagged chunks."""
    sents = _iter_sentence_records(layout)
    chunks: list[Chunk] = []
    for i, group in enumerate(_assemble_chunks(sents, target_tokens=target_tokens, overlap_tokens=overlap_tokens)):
        chunks.append(_build_chunk(document_id, i, group))
    return chunks


def chunk_parsed_dir(
    parsed_root: Path,
    out_root: Path,
    *,
    document_ids: Iterable[str] | None = None,
    target_tokens: int = 400,
    overlap_tokens: int = 40,
) -> dict[str, Path]:
    """Chunk every ``<parsed_root>/<document_id>/layout.json`` into
    ``<out_root>/<document_id>.jsonl``. Returns a map of document_id → output path.
    """
    parsed_root = Path(parsed_root)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    out_paths: dict[str, Path] = {}
    subset = set(document_ids) if document_ids else None
    for doc_dir in sorted(parsed_root.iterdir()):
        if not doc_dir.is_dir():
            continue
        if subset is not None and doc_dir.name not in subset:
            continue
        layout_path = doc_dir / "layout.json"
        if not layout_path.is_file():
            continue
        layout = json.loads(layout_path.read_text())
        chunks = chunk_document(
            doc_dir.name,
            layout,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )
        out_path = out_root / f"{doc_dir.name}.jsonl"
        with out_path.open("w") as f:
            for c in chunks:
                f.write(c.model_dump_json() + "\n")
        out_paths[doc_dir.name] = out_path
    return out_paths
