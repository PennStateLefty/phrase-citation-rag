"""Pydantic models shared across the pipeline.

IDs use stable, human-readable formats so they survive in prompts, logs,
and citation output:

    document_id : str   e.g. "irs_pub_17_2025"
    chunk_id    : str   e.g. "irs_pub_17_2025::p042::c03"
    sentence_id : str   e.g. "irs_pub_17_2025::p042::c03::s02"
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, NonNegativeInt


class Sentence(BaseModel):
    sentence_id: str
    chunk_id: str
    document_id: str
    text: str
    page: NonNegativeInt
    section_path: list[str] = Field(
        default_factory=list,
        description="Heading breadcrumbs from H1 -> deepest heading.",
    )
    char_start: NonNegativeInt
    char_end: NonNegativeInt
    embedding: list[float] | None = None


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    page: NonNegativeInt
    section_path: list[str] = Field(default_factory=list)
    text: str
    token_count: NonNegativeInt
    sentences: list[Sentence]
    embedding: list[float] | None = None


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float
    rerank_score: float | None = None


CitationSource = Literal["llm", "aligner"]


class Citation(BaseModel):
    sentence_id: str
    chunk_id: str
    document_id: str
    page: NonNegativeInt
    section_path: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    source: CitationSource


class CitedSentence(BaseModel):
    """One sentence of the generated answer, with its citations."""

    index: NonNegativeInt
    text: str
    citations: list[Citation] = Field(default_factory=list)


class CitedAnswer(BaseModel):
    question: str
    answer_text: str
    sentences: list[CitedSentence]
    strategy: Literal["inline_prompted", "post_gen_alignment"]
    model: str
    retrieved_chunk_ids: list[str]


class GroundTruthItem(BaseModel):
    question_id: str
    question: str
    difficulty: Literal["easy", "medium", "hard"]
    gold_answer: str
    # For each sentence in gold_answer (0-indexed), the set of supporting
    # source sentence_ids.
    gold_citations: list[list[str]]


class EvalResult(BaseModel):
    question_id: str
    strategy: Literal["inline_prompted", "post_gen_alignment"]
    precision: float
    recall: float
    f1: float
    coverage: float
    retrieval_recall_at_k: float
