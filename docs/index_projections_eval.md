# Index Layout Spike — Layout X vs Layout Y

**Status:** complete (qualitative). Formal recall@k against synthetic GT
is scheduled under `synth-gt-generator` / `eval-harness`; this document
captures the structural and cost comparison so the Phase 1a baseline
retrieval code can make an informed layout choice now.

## Layouts under test

### Layout X — chunk index with nested sentences (baseline, committed)

* One Azure AI Search index: **`tax-chunks`**.
* One document per chunk. Chunk-level 3072-d `chunk_vector`
  (text-embedding-3-large). Nested `sentences` complex collection carries
  each sentence's `sentence_id`, `text`, `page`, `char_start/end`,
  `section_path` inside the parent chunk document.
* Retrieval shape: hybrid (BM25 + vector) + semantic ranker on the chunk
  index, then the citation aligner (future step) scores each of the
  chunk's nested sentences against the generated claim to pick the
  specific `sentence_id` to cite.
* Pros: one index, cheap to build, no sentence-level embeddings,
  simpler ops. Every citation candidate is already tied to a chunk so
  context for generation is "free" — `text` and `sentences[]` arrive
  in the same hit.
* Cons: sentence-level retrieval precision is gated by chunk-level
  retrieval. A chunk that fails to be retrieved means **none** of its
  sentences can be cited — even if a single sentence inside it is a
  perfect match.

### Layout Y — projected per-sentence index (spike)

* Second Azure AI Search index: **`tax-sentences`**.
* One document per **unique** sentence (parent `chunk_id`,
  `document_id`, `page`, `section_path`, `text`, `token_count`,
  3072-d `sentence_vector`).
* Overlap sentences (which legitimately appear in two adjacent chunks)
  are stored once in the sentence index, keyed by `sentence_id`;
  parent `chunk_id` is the first-seen chunk. Retrieval counts from
  the live build: **69,424 sentences → 64,011 unique docs** indexed
  (7.8% overlap dedupe). See `sentcite.indexing._unique_sentences`.
* Retrieval shape: hybrid + semantic ranker directly on the sentence
  index. Each hit *is* the citation target. Parent context (full
  chunk `text` for the generator) is fetched by a second Search
  lookup on `tax-chunks` keyed by `chunk_id`, or by joining to the
  parsed chunks on disk.
* Pros: citation target is retrieved directly; recall on
  rare-but-specific claims (dollar figures, dates, percentages, form
  numbers) is less dependent on the chunk containing the sentence
  also being a chunk-level semantic match.
* Cons: 2× embedding bill, ~27× storage, longer index build, and the
  generator still needs chunk-level context (→ second Search call
  per hit, or keep Layout X alongside).

> **Note on terminology.** Azure AI Search has a first-class
> *skillset + indexProjections* feature that drives sentence-level
> child indexes from the indexer pipeline. We chose push-mode parity
> with the rest of the prototype (we already chunk + embed in code),
> so "Layout Y" here is a second pushed index, not a managed
> projection. If we ever switch to skillset-driven ingestion the same
> schema and decision logic apply.

## Measured numbers (live Swedish Central service)

Corpus: 10 IRS publications, 597 pages, 2,558 chunks, 69,424 sentences.

| Metric | Layout X (`tax-chunks`) | Layout Y (`tax-sentences`) |
| --- | --- | --- |
| Documents indexed | 2,558 | 64,011 |
| Storage size | 108 MB | 2,899 MB |
| Vector index size | 30 MB | 655 MB |
| Build wall time | ~9 min | ~80 min |
| Embedding calls (batch=64) | ~40 | ~1,085 |
| Median hybrid+semantic latency (top-10, 10 probes) | 1,215 ms | 1,229 ms |
| Max latency | 2,268 ms | 2,269 ms |

Ten hand-curated probe queries covered recordkeeping duration,
depreciation method, Section 179 limits, standard mileage rate,
statutory employees, home-office deductions, partnership allocations,
sole-prop vs LLC, and Form 941. See
[`index_projections_eval_results.json`](./index_projections_eval_results.json)
for the full dump.

### Qualitative findings

* **Both layouts land the right document** on every probe. No probe
  retrieved a hit from the wrong IRS publication on either layout.
* **Layout Y returns higher-signal snippets.** Example — *"standard
  mileage rate"*: Layout Y top hit is the literal sentence *"For 2025,
  the standard mileage rate … is 70 cents ($0.70) per mile"*
  (Pub 463, p.20). Layout X top hit is the containing chunk; the
  matching sentence is in there, but selecting it requires the
  downstream citation aligner.
* **Parent-chunk agreement: 0.63 mean, 0.30 min across 10 probes.**
  The top-10 sentences returned by Layout Y parent up to 10 distinct
  chunks; on average 63% of those parents also show up in Layout X's
  top-10. The cases where agreement drops below 0.5 are exactly the
  ones we expect Y to help: specific numeric facts that live in a
  long mixed-topic chunk (Section 179 limits surfaced via a "for tax
  years beginning in 2025" sentence that Pub 463 mentions in passing
  but wasn't a top-10 *chunk* for that query). This is qualitative
  evidence that Y extends recall on sentence-level queries beyond
  what X can do alone — but it needs synth-GT to quantify.
* **Layout Y is already the sentence-selection step.** If we commit to
  Y for retrieval, the citation aligner shifts from "pick a sentence
  out of the retrieved chunk" to "verify that the retrieved sentence
  actually supports the claim" — a simpler, more faithful task.

## Decision

* `sentcite.indexing` keeps both layouts as first-class.
  `ensure_chunks_index` / `upload_chunks` remain the baseline and
  `ensure_sentences_index` / `upload_sentences` are live. The
  `scripts/build_index.py --layout {chunks,sentences,both}` flag
  controls what gets populated.
* **Retrieval defaults to the hybrid dual-layout strategy** in code
  that lands under the `retrieval` todo:
  1. Retrieve top-`k_s` *sentences* from Layout Y as citation
     candidates (typically `k_s=20-30`).
  2. Aggregate their distinct parent `chunk_id`s (plus optional
     Layout X top-`k_c` chunks) and fetch the full chunk text from
     Layout X as the generator's context window.
  3. The citation aligner verifies each generated sentence against
     the candidate sentence pool.
  This gets us high sentence-level recall for citations while the
  generator still receives coherent chunk-sized context.
* **Storage and cost tradeoffs are acceptable at this corpus size.**
  Full re-embedding is ~$0.10 (760K sentence tokens at
  text-embedding-3-large) and ~1 hour wall-time. For a 10× larger
  corpus we would revisit: dimension reduction on the sentence vector
  (text-embedding-3-large supports runtime `dimensions` down to 256
  with minor quality loss), narrower-than-sentence granularity only
  for "hard" sentences, or moving sentence embedding into a skillset
  so Search manages the pipeline.

## Gaps / follow-ups

* **Formal recall@k requires synthetic GT.** Blocked on
  `synth-gt-generator`. The eval harness will replay both layouts
  against the same question set and report recall@1/@3/@10 and
  MRR, so the retrieval default can be validated (or overturned)
  with numbers.
* **Overlap dedup heuristic.** Currently *first-seen* wins when the
  same sentence appears in two chunks. If we later want richer
  context expansion we could store all parent `chunk_id`s in a
  collection field on the sentence doc.
* **Bicep drift.** `infra/main.bicep` still provisions the Search
  service with default auth; the AAD flip (`aadOrApiKey`) was done
  out-of-band. Captured as a follow-up in the plan.
* **Sentence index build is serial.** The ~80-min build is dominated
  by embedding round-trips. If we need to rebuild frequently we can
  parallelize the embeddings call (thread pool over docs) — deferred
  until we actually need it.
