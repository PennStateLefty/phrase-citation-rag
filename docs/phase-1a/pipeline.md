---
title: Pipeline
parent: Phase 1a
nav_order: 3
---

# Pipeline — technical walk-through
{: .no_toc }

<details markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## Components

The pipeline is six modules, each with a single responsibility.
Everything is idempotent, every stage writes its output to disk so
it can be re-run independently, and every component has tests.

```
PDFs  →  ingest/  →  parsed/*.json
                    → chunking.py → chunks/*.jsonl
                                    → indexing/   → Azure AI Search indexes
                                                    ↘
Question  →  retrieval.py  →  candidate pool  →  generate.py (strategy A or B)
                                                   →  cite_align.py (strategy B only)
                                                      →  CitedAnswer
                                                         →  judge.py / self_consistency.py / eval.py
```

## Infra

- **Resource group:** `rg-phrase-citation-testing`
- **Region:** `swedencentral`
- **Storage:** Azure Blob (raw PDFs + parsed JSON).
- **Document Intelligence:** Layout API, pre-built model.
- **AI Search:** two indexes (`tax-chunks` Layout-X,
  `tax-sentences` Layout-Y), semantic ranker enabled.
- **Model endpoints:** Microsoft Foundry AIServices, three role-
  bound deployments (`gpt-4.1-1`, `mistral-large-3`,
  `llama-3.3-70b-instruct`).
- **Auth:** `DefaultAzureCredential` end-to-end — no API keys in
  `.env`, everything is Entra ID token-based.

## Corpus

Phase 1a candidate corpus (IRS public documents):

- **Pub 587** — Business Use of Your Home
- **Pub 946** — How to Depreciate Property
- **Pub 463** — Travel, Gift, and Car Expenses
- **Pub 535** — Business Expenses *(referenced by 587 but not yet
  ingested)*
- **Form 8829 + instructions** — Expenses for Business Use of Your
  Home

This set is chosen because:

1. It's public and redistributable.
2. It has the cross-reference richness typical of tax auditing
   (Pub 587 constantly points at 946, 463, and 535).
3. The 8829 form + instructions let us test form-field questions
   distinct from pure publication prose.

The formal **corpus manifest** (with exact URLs, revision dates,
and per-document licence confirmation) is
[blocked on SME]({{ '/status/' | relative_url }}) because the SME
needs to confirm which documents are in-scope for the eventual
Phase 1b evaluation. The code is agnostic to which documents are
ingested.

## Ingest

`src/sentcite/ingest/` drives Azure Document Intelligence Layout
API per PDF. Output is a JSON document per PDF, preserving page
numbers, line bounding boxes, detected section headers, tables,
and reading-order spans.

**Human step:** none per document — the ingestion pass is fully
automated. Cost is billed per-page at Document Intelligence rates.

## Chunking

`src/sentcite/chunking.py`:

1. Sentence split with spaCy (a deterministic pipeline; we pin
   `en_core_web_sm` so sentence IDs are stable across re-ingest).
2. Chunk assembly: accrete sentences until we hit a target token
   budget, with section-boundary priority (we never span across a
   detected section heading). Target size ≈ 800 tokens, hard max
   1200.
3. Sentence IDs are of the form
   `<document_id>::<chunk_id>::s<NNN>`.

Chunking is pure — given the same parsed JSON, it produces the
same chunks and the same sentence IDs.

## Indexing

`src/sentcite/indexing/`:

- **Layout X (`tax-chunks`):** one document per chunk. Chunk text,
  chunk vector (3072-d, `text-embedding-3-large`), and a nested
  complex collection `sentences[]` carrying each sentence's text,
  sentence_id, page, and byte span.
- **Layout Y (`tax-sentences`):** one document per sentence.
  Sentence text + sentence vector (same embedding), plus a
  back-reference to the parent chunk_id.

Both indexes carry the same document scope. The indexer pushes
both from the same pass over the chunked output so they never
drift.

Index-projection spike results are in
[Index Projections Eval]({{ '/index-projections-eval/' | relative_url }}).

## Retrieval

`src/sentcite/retrieval.py` exposes a single `retrieve()` with
three modes:

- `mode="chunks"` — Layout X only, returns top-k chunks.
- `mode="sentences"` — Layout Y only, returns top-k sentences.
- `mode="dual"` (default) — query both indexes in parallel, return
  a `RetrievalResult` with both populated.

Each search uses:

1. BM25 text search.
2. Vector search on the relevant embedding.
3. Azure semantic reranker on the merged pool.

The returned `RetrievalResult` is the candidate pool for
generation.

## Generation

`src/sentcite/generate.py` implements both strategies:

### Strategy A — inline prompted

The system prompt instructs the model to emit citation markers
like `[s:<sentence_id>]` after every sentence, drawing only from a
list of `(sentence_id, text)` tuples supplied in the context. The
parser then reconstructs `CitedAnswer.sentences[*].citations`
directly from the model's markers.

**Pros:** one LLM call. Fast. No alignment drift.
**Cons:** the model is juggling two tasks at once; any hallucinated
or malformed marker requires retries/repair.

### Strategy B — post-generation alignment

Two steps:

1. The model writes a clean, citation-free answer.
2. `src/sentcite/cite_align.py` splits the answer into sentences
   and, for each one, computes cosine similarity against every
   sentence in the retrieval pool. The top-k over threshold τ
   become the citations.

**Pros:** clean separation of concerns. The aligner is
deterministic given the inputs. No prompt pressure on the
answerer.
**Cons:** aligner can miss the author's **exact** source
sentence when a parallel sentence is cosine-closer — this shows
up as low F1 against synth-GT even when the citation is still
honest.

Both strategies produce the same `CitedAnswer` shape so downstream
code is strategy-agnostic.

## Judging

`src/sentcite/judge.py` uses `llama-3.3-70b-instruct` to score
faithfulness. For each answer sentence, the judge sees:

- The answer sentence.
- The text of every citation attached to it.
- Nothing else (no access to the full answer, no access to the
  question's gold answer).

The judge emits `supported` / `partially_supported` /
`not_supported` per sentence, plus a short reason string. We
aggregate to `percent_faithful` (percent of answer sentences the
judge rated `supported`) and `percent_sentences_any_faithful`
(percent rated `supported` **or** `partially_supported`).

## Self-consistency

`src/sentcite/self_consistency.py`. For a single question:

1. Retrieve **once** (Azure Search is deterministic on a fixed
   query vector + top-k, and re-paying the retrieval cost N times
   would add nothing).
2. Run generation + citation **N times** (default 5) with
   `temperature > 0` so sampling varies.
3. Compute `stability = |∩ of citation-id sets| / |∪ of citation-
   id sets|` across the N runs.
4. Surface `stable_anchor_ids` — sentences cited in ≥ ⌈0.5 × N⌉
   runs. These are the citations a customer will see reliably.

Cost is roughly `N × (generate + cite)` per item, so self-
consistency is opt-in on the harness.

## Evaluation

`src/sentcite/eval.py` — see [evaluation]({{ '/phase-1a/evaluation/' | relative_url }}).

## Layperson review

`src/sentcite/layperson_review.py` + `scripts/review_gt.py`. See
the relevant sections of [evaluation]({{ '/phase-1a/evaluation/#layperson-review' | relative_url }}).

## Public-benchmark adapter

`src/sentcite/benchmarks.py`. Loads HAGRID or ALCE JSONL, wraps
each item as a `BenchmarkItem`, synthesises a local
`RetrievalResult` from the benchmark's packaged passages (no
Azure round-trip — the benchmark already decided the candidate
pool for us), runs the same generate + cite path, then scores at
**passage grain** — which is what HAGRID and ALCE actually
annotate. Emits the same `EvalReport` shape as the synth-GT
harness, so side-by-side reporting is trivial.

## Roles & human-in-the-loop touchpoints

| Component | Automated? | Human touchpoint |
| --- | --- | --- |
| Ingest | yes | — |
| Chunking | yes | — |
| Indexing | yes | — |
| Retrieval | yes | — |
| Generation (both strategies) | yes | — |
| Citation alignment | yes | — |
| **Synth-GT authoring** | yes (LLM-only) | layperson review — non-SME spot-check over 10–20 items |
| **Synth-GT judging** | yes (LLM-only) | — |
| LLM-as-judge faithfulness | yes | — |
| Self-consistency | yes | — |
| **Corpus scope sign-off** | no | **SME** (Phase 1b) |
| **Gold questions** | no | **SME** (Phase 1b) |
| **Gold answers + citations** | no | **SME** (Phase 1b) |
| **Inter-annotator agreement** | no | **two SMEs** (Phase 1b) |
| **Failure review** | partial | **SME** verdict on each failure (Phase 1b) |
| **Demo rehearsal** | no | PM + SME + AE |

Everything above the bold `SME` rows works today. Everything at or
below is the explicit Phase 1b scope.
