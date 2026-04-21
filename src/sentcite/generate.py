"""Answer generation under both citation strategies.

Two strategies are implemented, feeding the same downstream evaluation:

* **Strategy A — ``inline_prompted``.** The RAG generator is asked to
  emit inline ``[s:<sentence_id>]`` tags after every claim that is
  supported by a source sentence. The system prompt labels each
  source sentence in the context with its sentence_id so the model
  has the vocabulary to cite from. Tag parsing + validation happens
  in :mod:`sentcite.cite_align`.
* **Strategy B — ``post_gen_alignment``.** The model is asked for a
  plain answer with no citation tags; ``cite_align`` post-hoc-aligns
  each answer sentence against the candidate pool.

Both strategies consume the same :class:`~sentcite.retrieval.RetrievalResult`
produced by :func:`sentcite.retrieval.retrieve`, and both produce a
:class:`GenerateOutput` with the raw model text plus enough provenance
(retrieved chunk IDs, candidate sentence IDs, model identity) that the
alignment + eval stages don't need to re-retrieve anything.

Auth + model selection: :func:`sentcite.llm.get_client` (RAG role).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage

from .config import AzureConfig
from .llm import get_binding, get_client
from .retrieval import RetrievalResult

Strategy = Literal["inline_prompted", "post_gen_alignment"]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


SYSTEM_A = (
    "You are a tax-audit research assistant. Answer the user's question "
    "using ONLY the information in the sources provided below. Every "
    "source sentence is labeled with a unique id in the form "
    "[s:<sentence_id>]. Your answer MUST obey these rules:\n"
    "1. Break your answer into short, factual sentences. One claim per sentence.\n"
    "2. Immediately after each sentence that is supported by the sources, "
    "append one or more tags of the form [s:<sentence_id>] citing the "
    "specific source sentence(s) that support that claim. Use only IDs "
    "that appear in the Sources section.\n"
    "3. If the sources do not answer the question, reply with exactly: "
    "'INSUFFICIENT SOURCES.' and nothing else.\n"
    "4. Do not invent facts. Do not cite IDs that are not in the Sources.\n"
    "5. Do not include preamble or postscript — just the answer sentences "
    "and their citations."
)

SYSTEM_B = (
    "You are a tax-audit research assistant. Answer the user's question "
    "using ONLY the information in the sources provided below. Keep the "
    "answer concise and factual — one claim per sentence. Do not include "
    "citation markers, source references, or footnotes; the answer will be "
    "aligned to the sources automatically. If the sources do not answer the "
    "question, reply with exactly: 'INSUFFICIENT SOURCES.' and nothing else."
)


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


def _section_label(section_path: list[str]) -> str:
    if not section_path:
        return ""
    return " > ".join(section_path)


def build_context_block(
    result: RetrievalResult,
    *,
    include_sentence_ids: bool,
    max_chars_per_chunk: int | None = None,
) -> tuple[str, list[str]]:
    """Render the retrieval context for the generator.

    Returns ``(context_text, sentence_ids_in_order)``. When
    ``include_sentence_ids`` is True (Strategy A), each source sentence
    is prefixed with its ``[s:<sentence_id>]`` tag so the model can
    cite it. When False (Strategy B), the chunk text is shown as a
    normal paragraph.

    The list of sentence ids in the order they appear in the context
    is also returned — Strategy A's tag parser uses it as the
    allowed-citations whitelist.
    """
    lines: list[str] = []
    all_sent_ids: list[str] = []
    for i, c in enumerate(result.chunks, start=1):
        header = f"[Chunk {i}: {c.chunk_id} | doc={c.document_id}"
        label = _section_label(c.section_path)
        if label:
            header += f" | {label}"
        header += f" | p.{c.page}]"
        lines.append(header)

        if include_sentence_ids and c.sentences:
            for s in c.sentences:
                sid = s.get("sentence_id") or ""
                text = (s.get("text") or "").strip()
                if not sid or not text:
                    continue
                all_sent_ids.append(sid)
                lines.append(f"[s:{sid}] {text}")
        else:
            body = c.text.strip()
            if max_chars_per_chunk and len(body) > max_chars_per_chunk:
                body = body[:max_chars_per_chunk].rstrip() + " …"
            lines.append(body)
        lines.append("")  # blank line between chunks
    return "\n".join(lines).rstrip(), all_sent_ids


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class GenerateOutput:
    question: str
    strategy: Strategy
    answer_text: str
    model: str
    retrieved_chunk_ids: list[str]
    # Sentence IDs that appeared in the context window (Strategy A
    # whitelist; useful diagnostic for B too).
    context_sentence_ids: list[str] = field(default_factory=list)
    # Sentence IDs from Layout Y's ranked candidate pool (for ablation).
    candidate_sentence_ids: list[str] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: float = 0.0
    finish_reason: str | None = None


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _complete(
    client: ChatCompletionsClient,
    *,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
):
    return client.complete(
        model=model,
        messages=[SystemMessage(content=system), UserMessage(content=user)],
        temperature=temperature,
        max_tokens=max_tokens,
    )


def generate(
    question: str,
    result: RetrievalResult,
    *,
    strategy: Strategy,
    cfg: AzureConfig | None = None,
    client: ChatCompletionsClient | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> GenerateOutput:
    """Generate an answer under the given strategy.

    ``result`` is the retrieval output: its ``chunks`` list supplies
    the context block (with per-sentence IDs for Strategy A) and its
    ``sentence_candidates`` become the Layout Y whitelist. The RAG
    binding (``cfg.openai_chat_deployment``) is the single model
    invoked here; the synth-GT and judge roles are deliberately not
    called from this path.
    """
    cfg = cfg or AzureConfig.from_env()
    binding = get_binding("rag", cfg)
    client = client or get_client("rag", cfg)

    include_ids = strategy == "inline_prompted"
    context_text, ctx_sent_ids = build_context_block(
        result, include_sentence_ids=include_ids
    )

    system = SYSTEM_A if strategy == "inline_prompted" else SYSTEM_B
    user = (
        f"Question: {question}\n\n"
        f"Sources:\n{context_text}\n\n"
        f"Answer:"
    )

    t0 = time.perf_counter()
    resp = _complete(
        client,
        model=binding.deployment or binding.model_identity,
        system=system,
        user=user,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    dt = (time.perf_counter() - t0) * 1000

    choice = resp.choices[0]
    answer = (choice.message.content or "").strip()
    usage = getattr(resp, "usage", None)

    return GenerateOutput(
        question=question,
        strategy=strategy,
        answer_text=answer,
        model=binding.model_identity,
        retrieved_chunk_ids=result.candidate_chunk_ids(),
        context_sentence_ids=ctx_sent_ids,
        candidate_sentence_ids=result.candidate_sentence_ids(),
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        latency_ms=dt,
        finish_reason=getattr(choice, "finish_reason", None),
    )
