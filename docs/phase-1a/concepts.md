---
title: Concepts
parent: Phase 1a
nav_order: 2
---

# Concepts & glossary
{: .no_toc }

A layperson-friendly glossary of every term that shows up in the
customer deck and in the code.

<details markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## RAG (Retrieval-Augmented Generation)

An AI pattern where, instead of asking a language model to answer
from memory, you first **retrieve** relevant source documents and
then ask the model to **generate** an answer using only those
sources. Reduces hallucination and lets you show where the answer
came from.

## Citation

A pointer from an AI-generated answer sentence to the source
sentence that supports it. Phase 1a aims for **sentence-level**
citations (pointing at one specific sentence in one specific
publication on one specific page) rather than the more common
**document-level** or **page-level** citations.

## Ground truth (GT)

The "correct answer" for each test question, including which source
sentences should be cited. Phase 1a uses **synthetic GT** produced
by an author model and self-judged by a judge model. Phase 1b will
use **SME-authored GT** — the real thing, written by a tax expert.

## Strategy A — "inline prompted"

The answer model is asked to emit citation markers as it writes, in
a structured format (e.g. `[s:abc-123]`). One LLM call, fast, but
the model has to juggle writing the answer **and** picking
citations simultaneously.

## Strategy B — "post-generation alignment"

Two steps. Step 1: the model writes a clean, citation-free answer.
Step 2: an **aligner** takes each answer sentence and finds the
best-matching source sentence(s) in the retrieved pool via cosine
similarity, then attaches those as citations. More deterministic,
but can "miss" when the author actually composed from a source that
isn't the top cosine match.

## Faithfulness

"Does the cited source actually back up what the answer claims?"
Measured by showing each answer sentence + its citations to a
**separate** language model (the "judge") that has no stake in
making the answerer look good, and asking it to vote `supported`
/ `partially_supported` / `not_supported`. We report the percentage
of answer sentences rated `supported`.

{: .important }
> Faithfulness uses a **different** model from the one that wrote
> the answer (currently `llama-3.3-70b-instruct` as judge vs
> `gpt-4.1-1` as answerer). Using the same model for both would
> be marking your own homework.

## Stability / self-consistency

"If I ask the same question five times, do I get the same
citations?" We re-run generation with temperature > 0 so sampling
varies, then compute the intersection-over-union of citation IDs
across runs. Reported as a number from 0.0 (completely different
every time) to 1.0 (identical every run).

Customers care about stability because an auditor who sees one
citation on Monday and a different one on Tuesday will stop
trusting the tool.

## Precision / Recall / F1 (against GT)

Standard information-retrieval metrics, applied to the **set of
cited sentence IDs**:

- **Precision** — of the sentences the system cited, what fraction
  were in the ground truth? ("Did we cite junk?")
- **Recall** — of the ground-truth sentences, what fraction did we
  cite? ("Did we miss anything?")
- **F1** — the harmonic mean of precision and recall.

{: .note }
> Against **synthetic** ground truth, F1 is systematically
> pessimistic: the synth-GT captures the author model's exact
> provenance span, and our aligner often cites an adjacent or
> parallel sentence that supports the same claim. Set-F1 penalises
> that even though the citation is genuinely helpful. This is the
> single biggest reason we lead with faithfulness in customer
> conversations.

## Coverage

Of the sentences in the AI's answer, what fraction got at least one
citation attached? Low coverage = the system is producing
un-sourced assertions. We expect coverage close to 1.0 under both
strategies.

## Retrieval Recall @ k (R@k)

Of the ground-truth source sentences, how many were reachable in
the top-k retrieval pool the generator was allowed to cite? This is
the **ceiling** on recall — if the right sentence wasn't retrieved,
the citation stage can't possibly cite it. Separating retrieval
recall from citation recall tells us whether to fix retrieval or
the citation step when F1 is low.

## Candidate pool

The list of chunks + sentences that retrieval hands to the
generator as "you may cite any of these." Typically ~20 sentences
and ~5 chunks per question.

## Chunk vs. sentence

- A **chunk** is a passage of ~500–1000 tokens, chosen to be
  semantically coherent (usually bounded by section headings).
- A **sentence** is what it sounds like, identified by spaCy.

Every sentence lives inside exactly one chunk. Both are indexed;
the generator gets both.

## Layout X vs. Layout Y

Two Azure AI Search index layouts we maintain in parallel:

- **Layout X** — one document per chunk, with nested sentences as a
  complex-collection field. Vector is at the chunk level.
- **Layout Y** — one document per sentence, with the parent chunk
  referenced by ID. Vector is at the sentence level.

Having both lets us do dual-grain retrieval in a single query and
pick whichever grain the downstream citation step prefers.

## Judge model

The language model that scores **faithfulness**. Deliberately
chosen to be different from the answer model and the synth-GT
author model, so the whole three-role separation (answerer,
synth-GT author, judge) prevents any one model from
self-certifying.

## Three-role LLM factory

A small abstraction in `src/sentcite/llm.py` that makes sure every
piece of code uses the correct model for its role:

- `rag` → `gpt-4.1-1` (writes answers)
- `synth_gt` → `mistral-large-3` (writes synthetic ground truth)
- `judge` → `llama-3.3-70b-instruct` (scores faithfulness)

The factory enforces distinct `model_identity` values so a
regression that accidentally routes judge calls through the
answerer model fails loudly.

## Synthetic GT

Ground-truth items produced without an SME. One model writes the
question from a source passage, another model writes the gold
answer, a third judges whether the result is well-formed and
supported. Suitable for debugging the pipeline; **not** suitable
for headline customer accuracy claims.

## Layperson review

A non-SME spot-check over 10–20 synthetic GT items. A reviewer
(ML-Eng or PM) looks at each item and tags it with a confidence
rating (`high` / `medium` / `low`) plus optional flags
(`citation_mismatch`, `gold_answer_wrong`, etc.). The review
**does not** claim tax-law correctness — it catches obviously
broken items that a human would recognise as "that's not even
trying to answer the question." Surfaced in reports with an
explicit **non-SME** label.

## SME (Subject Matter Expert)

A qualified tax professional (attorney, CPA, enrolled agent, or
experienced auditor). Their involvement is the gating dependency
for Phase 1b: without SME-authored questions and answers, we
cannot claim tax-law accuracy, only pipeline-level consistency.

## Union additions

When both an author model and a judge model independently
identify source sentences supporting an answer, the union of their
picks becomes the "gold citations" for that answer sentence. This
dampens the "author model forgot to cite a sentence that was
clearly supporting" failure mode without over-inflating the gold
set.

## Difficulty tier

Every synth-GT item is tagged `easy` / `medium` / `hard` at
generation time based on how many source sentences are required to
produce the gold answer. Aggregate metrics are reported per tier
so a headline F1 isn't dominated by easy items.

## Public benchmark (HAGRID, ALCE)

Third-party sentence-attribution benchmarks with human-validated
gold citations. HAGRID (Huggingface) and ALCE (Princeton) both
publish questions plus candidate passages plus human-annotated
attribution. Our benchmark adapter scores at passage grain, which
is what those benchmarks annotate — so our numbers on HAGRID are
directly comparable with numbers in the published literature.

Useful because it gives the customer a point of reference
("sentence-level citation is a known-hard problem, here's the
state of the art") that doesn't depend on the synth-GT caveat.
