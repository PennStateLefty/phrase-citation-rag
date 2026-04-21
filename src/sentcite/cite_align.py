"""Map generated answer sentences to source sentence_ids.

Two entry points mirror the two generation strategies, and both emit
the same :class:`~sentcite.schema.CitedAnswer` so downstream eval code
treats them uniformly.

Strategy A — :func:`parse_inline_citations`
    Parse ``[s:<sentence_id>]`` tags the RAG model emits inline.
    Validate each cited id against the context whitelist
    (``GenerateOutput.context_sentence_ids``). Strip tags to produce
    the clean answer text and spaCy-split it; attribute each tag to
    the answer sentence it falls inside. Hallucinated ids (not in
    the whitelist) are dropped and counted.

Strategy B — :func:`align_post_generation`
    spaCy-split the answer text, embed each answer sentence, cosine-
    score against the Layout Y sentence candidate pool, keep matches
    with ``cosine >= tau`` (default 0.75), top-``k`` per answer
    sentence. ``source="aligner"`` and ``confidence`` = cosine.

The unified :func:`cite_answer` dispatches by
``GenerateOutput.strategy`` so callers don't need to branch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .chunking import split_sentences
from .config import AzureConfig
from .generate import GenerateOutput
from .indexing import embed_texts
from .retrieval import ChunkHit, RetrievalResult, SentenceHit
from .schema import Citation, CitedAnswer, CitedSentence

DEFAULT_TAU = 0.75
DEFAULT_TOPK = 3

TAG_RE = re.compile(r"\[s:([^\]\s]+?)\]")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SentenceMeta:
    sentence_id: str
    chunk_id: str
    document_id: str
    page: int
    section_path: tuple[str, ...]
    text: str


def _collect_sentence_meta(result: RetrievalResult) -> dict[str, _SentenceMeta]:
    """Build a sentence_id -> metadata map.

    Draws from both the flat Layout Y candidate list (preferred, richer
    fields) and the nested sentences on each Layout X chunk (fallback
    for the context whitelist). Candidate pool wins on conflict since
    it's the ranked, hybrid+semantic result.
    """
    meta: dict[str, _SentenceMeta] = {}
    # Nested sentences (whitelist scope).
    for c in result.chunks:
        for s in c.sentences or []:
            sid = s.get("sentence_id")
            if not sid:
                continue
            meta.setdefault(
                sid,
                _SentenceMeta(
                    sentence_id=sid,
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    page=int(s.get("page") or c.page or 0),
                    section_path=tuple(s.get("section_path") or c.section_path or []),
                    text=(s.get("text") or "").strip(),
                ),
            )
    # Flat candidates override (carries its own scores / trusted text).
    for s in result.sentence_candidates:
        meta[s.sentence_id] = _SentenceMeta(
            sentence_id=s.sentence_id,
            chunk_id=s.chunk_id,
            document_id=s.document_id,
            page=int(s.page or 0),
            section_path=tuple(s.section_path or []),
            text=(s.text or "").strip(),
        )
    return meta


def _build_cited_answer(
    *,
    question: str,
    answer_text: str,
    sentences: list[CitedSentence],
    strategy: str,
    model: str,
    retrieved_chunk_ids: list[str],
) -> CitedAnswer:
    return CitedAnswer(
        question=question,
        answer_text=answer_text,
        sentences=sentences,
        strategy=strategy,  # type: ignore[arg-type]
        model=model,
        retrieved_chunk_ids=list(retrieved_chunk_ids),
    )


# ---------------------------------------------------------------------------
# Strategy A — inline tag parser + validator
# ---------------------------------------------------------------------------


@dataclass
class InlineParseReport:
    total_tags: int = 0
    valid_tags: int = 0
    hallucinated_ids: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.hallucinated_ids is None:
            self.hallucinated_ids = []


def _strip_tags_with_positions(
    text: str,
) -> tuple[str, list[tuple[int, str]]]:
    """Remove all ``[s:<id>]`` tags; return clean text + tag anchors.

    Each anchor is ``(clean_pos, sentence_id)`` where ``clean_pos`` is
    the offset in the clean (tag-stripped) text at which the tag was
    originally located. Repeated tags (back-to-back ``[s:a][s:b]``)
    produce multiple anchors at the same ``clean_pos``.
    """
    out: list[str] = []
    anchors: list[tuple[int, str]] = []
    cursor = 0
    clean_len = 0
    for m in TAG_RE.finditer(text):
        out.append(text[cursor:m.start()])
        clean_len += m.start() - cursor
        anchors.append((clean_len, m.group(1)))
        cursor = m.end()
    out.append(text[cursor:])
    return "".join(out), anchors


def _attribute_tags_to_sentences(
    clean_text: str,
    anchors: list[tuple[int, str]],
) -> list[list[str]]:
    """Return list[list[str]] — cited ids per answer sentence.

    Answer sentences are obtained from spaCy. A tag at ``clean_pos``
    is attributed to the sentence whose ``(char_start, char_end)``
    contains it; if the tag sits in trailing whitespace / at the very
    end of the text it is attributed to the previous sentence.
    """
    sents = split_sentences(clean_text)
    if not sents:
        return []
    ids_per_sentence: list[list[str]] = [[] for _ in sents]
    for pos, sid in anchors:
        # Find the sentence whose span contains (or most recently ended
        # at) pos. Because tags usually land just after the period and
        # whitespace, "most-recent end <= pos" is the right rule.
        target = 0
        for i, (start, end, _) in enumerate(sents):
            if start <= pos < end:
                target = i
                break
            if end <= pos:
                target = i
        ids_per_sentence[target].append(sid)
    return ids_per_sentence


def parse_inline_citations(
    gen: GenerateOutput,
    result: RetrievalResult,
) -> tuple[CitedAnswer, InlineParseReport]:
    """Parse inline ``[s:<id>]`` tags and return a CitedAnswer.

    The whitelist is ``gen.context_sentence_ids`` — the ids the
    generator was actually allowed to cite. Ids outside that set are
    treated as hallucinations and dropped from the citations, but are
    reported in :class:`InlineParseReport` so the eval harness can
    measure drift.
    """
    if gen.strategy != "inline_prompted":
        raise ValueError(
            f"parse_inline_citations expects strategy='inline_prompted', got {gen.strategy!r}"
        )

    whitelist = set(gen.context_sentence_ids)
    meta = _collect_sentence_meta(result)

    clean_text, anchors = _strip_tags_with_positions(gen.answer_text)
    report = InlineParseReport(total_tags=len(anchors))
    ids_per_sent = _attribute_tags_to_sentences(clean_text, anchors)
    sents = split_sentences(clean_text)

    cited: list[CitedSentence] = []
    for idx, ((_, _, sent_text), ids) in enumerate(zip(sents, ids_per_sent)):
        citations: list[Citation] = []
        seen: set[str] = set()
        for sid in ids:
            if sid in whitelist and sid in meta:
                report.valid_tags += 1
                if sid in seen:
                    continue
                seen.add(sid)
                m = meta[sid]
                citations.append(
                    Citation(
                        sentence_id=m.sentence_id,
                        chunk_id=m.chunk_id,
                        document_id=m.document_id,
                        page=m.page,
                        section_path=list(m.section_path),
                        confidence=1.0,
                        source="llm",
                    )
                )
            else:
                report.hallucinated_ids.append(sid)
        cited.append(CitedSentence(index=idx, text=sent_text, citations=citations))

    answer = _build_cited_answer(
        question=gen.question,
        answer_text=clean_text.strip(),
        sentences=cited,
        strategy="inline_prompted",
        model=gen.model,
        retrieved_chunk_ids=gen.retrieved_chunk_ids,
    )
    return answer, report


# ---------------------------------------------------------------------------
# Strategy B — post-hoc cosine alignment
# ---------------------------------------------------------------------------


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1.0, norms)
    return mat / norms


def _candidate_pool(result: RetrievalResult) -> list[SentenceHit]:
    """The pool that Strategy B aligns against.

    Prefer the ranked ``sentence_candidates`` (Layout Y output). When
    retrieval ran in ``mode='chunks'`` we fall back to the nested
    sentences on the chunks so the aligner still has a pool.
    """
    if result.sentence_candidates:
        return list(result.sentence_candidates)
    pool: list[SentenceHit] = []
    for c in result.chunks:
        for s in c.sentences or []:
            sid = s.get("sentence_id")
            if not sid:
                continue
            pool.append(
                SentenceHit(
                    sentence_id=sid,
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    page=int(s.get("page") or c.page or 0),
                    section_path=list(s.get("section_path") or c.section_path or []),
                    text=(s.get("text") or "").strip(),
                )
            )
    return pool


def align_post_generation(
    gen: GenerateOutput,
    result: RetrievalResult,
    *,
    cfg: AzureConfig | None = None,
    tau: float = DEFAULT_TAU,
    top_k: int = DEFAULT_TOPK,
    answer_embeddings: Iterable[list[float]] | None = None,
    candidate_embeddings: Iterable[list[float]] | None = None,
) -> CitedAnswer:
    """Post-hoc cosine alignment for Strategy B.

    Per answer sentence: cosine similarity against the candidate
    sentence pool → filter by ``>= tau`` → keep top-``top_k``. The
    caller may supply pre-computed embeddings for either side (useful
    in tests and when candidate vectors are cached from retrieval).
    """
    if gen.strategy != "post_gen_alignment":
        raise ValueError(
            f"align_post_generation expects strategy='post_gen_alignment', got {gen.strategy!r}"
        )

    cfg = cfg or AzureConfig.from_env()
    answer_sents = split_sentences(gen.answer_text)
    pool = _candidate_pool(result)

    # Empty answer or empty pool → emit the answer sentences with no
    # citations (caller may still want the structure).
    if not answer_sents or not pool:
        cited = [
            CitedSentence(index=i, text=txt, citations=[])
            for i, (_, _, txt) in enumerate(answer_sents)
        ]
        return _build_cited_answer(
            question=gen.question,
            answer_text=gen.answer_text.strip(),
            sentences=cited,
            strategy="post_gen_alignment",
            model=gen.model,
            retrieved_chunk_ids=gen.retrieved_chunk_ids,
        )

    if answer_embeddings is None:
        answer_embeddings = embed_texts([t for _, _, t in answer_sents], cfg=cfg)
    if candidate_embeddings is None:
        candidate_embeddings = embed_texts([s.text for s in pool], cfg=cfg)

    A = _l2_normalize(np.asarray(list(answer_embeddings), dtype=np.float32))
    B = _l2_normalize(np.asarray(list(candidate_embeddings), dtype=np.float32))
    # (n_answer, n_candidates) cosine scores.
    sims = A @ B.T

    cited: list[CitedSentence] = []
    for i, (_, _, sent_text) in enumerate(answer_sents):
        row = sims[i]
        order = np.argsort(-row)
        citations: list[Citation] = []
        for j in order:
            score = float(row[j])
            if score < tau:
                break
            cand = pool[int(j)]
            citations.append(
                Citation(
                    sentence_id=cand.sentence_id,
                    chunk_id=cand.chunk_id,
                    document_id=cand.document_id,
                    page=int(cand.page or 0),
                    section_path=list(cand.section_path or []),
                    confidence=max(0.0, min(1.0, score)),
                    source="aligner",
                )
            )
            if len(citations) >= top_k:
                break
        cited.append(CitedSentence(index=i, text=sent_text, citations=citations))

    return _build_cited_answer(
        question=gen.question,
        answer_text=gen.answer_text.strip(),
        sentences=cited,
        strategy="post_gen_alignment",
        model=gen.model,
        retrieved_chunk_ids=gen.retrieved_chunk_ids,
    )


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------


def cite_answer(
    gen: GenerateOutput,
    result: RetrievalResult,
    *,
    cfg: AzureConfig | None = None,
    tau: float = DEFAULT_TAU,
    top_k: int = DEFAULT_TOPK,
) -> CitedAnswer:
    """Dispatch by strategy and return a :class:`CitedAnswer`.

    Strategy A: parse inline tags. Strategy B: post-hoc embed + align.
    """
    if gen.strategy == "inline_prompted":
        answer, _report = parse_inline_citations(gen, result)
        return answer
    return align_post_generation(gen, result, cfg=cfg, tau=tau, top_k=top_k)
