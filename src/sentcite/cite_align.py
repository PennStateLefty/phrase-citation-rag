"""Map generated answer sentences to source sentence_ids.

Two entrypoints mirror the two generation strategies:

- `parse_inline_citations`   — Strategy A: parse `[s_<id>]` tags emitted
  by the model; validate every cited id appears in the retrieved context.
- `align_post_generation`    — Strategy B: spaCy-split the answer, embed
  each sentence, cosine-match against source sentences, threshold at
  `tau` (default 0.75), return top-`k` matches as Citations.
"""

from __future__ import annotations

from .schema import CitedAnswer, RetrievedChunk

DEFAULT_TAU = 0.75
DEFAULT_TOPK = 3


def parse_inline_citations(
    question: str, answer_with_tags: str, context: list[RetrievedChunk], *, model: str
) -> CitedAnswer:
    raise NotImplementedError


def align_post_generation(
    question: str,
    answer_text: str,
    context: list[RetrievedChunk],
    *,
    model: str,
    tau: float = DEFAULT_TAU,
    top_k: int = DEFAULT_TOPK,
) -> CitedAnswer:
    raise NotImplementedError
