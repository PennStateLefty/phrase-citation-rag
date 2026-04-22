---
title: Overview
parent: Phase 1a
nav_order: 1
---

# Phase 1a in plain language
{: .no_toc }

<details markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

{: .tip }
> **Walk through it yourself.** Every stage described below has a
> corresponding notebook — see the full
> [notebook index]({{ '/notebooks/' | relative_url }}). If you are
> not an engineer, start with
> [`demo_02_pipeline_tour.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/demo_02_pipeline_tour.ipynb);
> it runs from a cached bundle so no Azure setup is required.

## Why this prototype exists

Tax auditors are trained to **show their work**. Every determination
they make has to be traceable to a specific rule in a specific
publication on a specific page. AI assistants that just say "yes, the
deduction is allowed" are not usable in that workflow — the auditor
still has to open the publication and re-verify the claim by hand,
which typically takes longer than just researching the answer
themselves.

The prototype tests a single idea:

> **If the AI cites its sources at the sentence level, verification
> becomes fast enough to be worth doing.**

"Sentence level" is the key constraint. Page-level citations
("somewhere on page 14 of Pub 587") are what most current RAG
products produce, and they are not enough — page 14 often contains
half a dozen paragraphs about unrelated things, so the auditor still
has to read the whole page. Sentence-level citations point at the
exact sentence, so the auditor's verification step collapses to
"read one sentence, decide if it actually says what the AI claimed."

## What the pipeline does, in six steps

### 1. Ingest
Raw PDF files (IRS publications) go through **Azure Document
Intelligence** to produce structured JSON — each page broken into
paragraphs, tables, headers, and so on.

### 2. Chunk
The parsed pages get split into **chunks** (roughly a
semantically-coherent passage, ~500–1000 tokens), and each chunk is
further split into **sentences** using spaCy. Every sentence gets a
stable ID so we can point back to it later.

### 3. Index
Both chunks and sentences are stored in **Azure AI Search**, with
vector embeddings and full-text tokens. Two layouts are maintained
in parallel ("Layout X" and "Layout Y") so the retrieval code can
query whichever is more useful for a given strategy.

### 4. Retrieve
When a question comes in, the pipeline does a **hybrid search**
(keywords + semantic similarity + reranking) to pull the most
relevant chunks and sentences — these are the "candidate pool" the
answer model is allowed to cite.

### 5. Generate
A language model (`gpt-4.1-1`) writes an answer to the question,
reading only from the retrieved candidate pool. Two strategies are
tried:

- **Inline prompted.** The model is told: "As you write, attach a
  citation marker to every sentence." Citations come out in the same
  pass as the answer.
- **Post-generation alignment.** The model writes a clean answer
  first. Then a separate step runs each answer sentence against the
  candidate pool and picks the best-matching source sentences as the
  citation.

Both are implemented and compared head-to-head.

### 6. Evaluate
We score the answers four ways:

- **Set-level F1** against ground truth (how well the cited
  sentences match the "correct" ones).
- **Coverage** — fraction of answer sentences that got any citation
  at all.
- **Faithfulness** — a separate LLM (`llama-3.3-70b-instruct`)
  reads each answer sentence and its cited support, and votes on
  whether the support actually backs the claim.
- **Stability** — we re-run the same question five times with
  random sampling on, then compare how much the citation set drifts.
  Stable citations mean an auditor sees the same answer twice in a
  row; unstable citations are a red flag.

## The important honesty caveat

Phase 1a's "ground truth" is **synthetic**: one model writes the
question, a different model writes the gold answer, and a third
model judges whether the result is well-formed. This is fine for
debugging the pipeline and for relative comparisons between
strategies — but **it is not a tax-law accuracy claim**.

The customer deck intentionally leads with **faithfulness** (the
cited sentence actually supports the claim, as judged by a
different model) and **stability** (the pipeline gives the same
answer twice). Both of those metrics survive the "we don't have SME
labels yet" caveat, because they're not asking "is this tax-law
correct?" — they're asking "is the pipeline internally consistent
about its own citations?"

Bringing in an SME unlocks the final accuracy number. That work is
the explicit scope of Phase 1b.

## What "good" looks like on a demo

When you open a run of `scripts/run_eval.py`, the headline table
looks like this:

| Metric | inline_prompted | post_gen_alignment |
| --- | --- | --- |
| Precision | 0.xxx | 0.xxx |
| Recall | 0.xxx | 0.xxx |
| F1 | 0.xxx | 0.xxx |
| Coverage | 0.xxx | 0.xxx |
| Retrieval R@k | 0.xxx | 0.xxx |
| Faithful % | 0–100 | 0–100 |
| Stability | 0.xxx | 0.xxx |

The ideal customer story on the demo is: **high faithfulness, high
stability, broad coverage, and low latency** — with the F1 numbers
presented as supporting evidence rather than the headline.

See [results]({{ '/phase-1a/results/' | relative_url }}) for the
actual current numbers and how to read them.
