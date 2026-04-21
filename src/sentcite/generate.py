"""Answer generation under the two citation strategies.

- Strategy A (`inline_prompted`): the system prompt instructs GPT-4o to
  emit `[s_<sentence_id>]` tags inline after each supported claim.
- Strategy B (`post_gen_alignment`): plain answer with no citation tags;
  citations come from `cite_align.align_post_generation`.
"""

from __future__ import annotations

from typing import Literal

from .schema import RetrievedChunk

Strategy = Literal["inline_prompted", "post_gen_alignment"]


def generate_answer(
    question: str, context: list[RetrievedChunk], *, strategy: Strategy
) -> str:
    raise NotImplementedError
