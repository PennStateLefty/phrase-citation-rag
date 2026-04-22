---
title: Evaluation
parent: Phase 1a
nav_order: 4
---

# Evaluation — metrics & harness
{: .no_toc }

<details markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## The harness in one call

```bash
python scripts/run_eval.py \
    --gt data/ground_truth/synthetic/phase1a-100-qg/items_reviewed.jsonl \
    --only-passing \
    --include-faithfulness \
    --include-self-consistency \
    --reviews data/ground_truth/synthetic/phase1a-100-qg/reviews.jsonl \
    --out data/eval \
    --run-id phase1a-full
```

Produces `data/eval/phase1a-full/` with:

- `items.jsonl` — one line per (question × strategy) with every raw
  score, the full cited answer, pred citation IDs, judge verdict,
  stability report, and reviewer metadata if present.
- `manifest.json` — machine-readable summary with model IDs,
  retrieval config, elapsed time, and all macro aggregates.
- `summary.md` — the customer-deck-ready markdown comparison table.

## Metrics, in one sentence each

| Metric | Question it answers |
| --- | --- |
| **Precision** | Of the sentences the system cited, what fraction are in the gold set? |
| **Recall** | Of the gold sentences, what fraction did the system cite? |
| **F1** | Harmonic mean of precision and recall. |
| **Coverage** | Of the system's answer sentences, what fraction got any citation? |
| **Retrieval R@k** | Were the gold sentences even reachable in the candidate pool? |
| **Faithful %** | What % of answer sentences did the judge rate as actually supported by their citations? |
| **Stability** | How similar are the citation sets across 5 re-runs at temperature 0.7? |

## Why F1 against synth-GT is pessimistic

The synth-GT gold is "the exact sentences the **author model** used
to compose the gold answer." The aligner (Strategy B) frequently
cites a parallel sentence that supports the same claim just as
well, or an adjacent sentence in the same paragraph. Those
citations are still correct — they're just not the author's exact
pick.

Example from a smoke run:

- Question: "What is the 2025 business-use mileage rate?"
- Author's source span: sentence `s042` ("The 2025 standard
  mileage rate for business use of a car is 70 cents per mile.")
- Aligner picked: sentence `s043` ("Taxpayers may use 70 cents per
  mile in lieu of actual expenses for business use in 2025.")

Under set-F1 this scores 0/1 → F1 = 0.0. The judge rates both as
`supported`.

This is why the customer deck leads with **faithfulness** and
**stability**, and reports F1 alongside with the caveat.

## The three-role separation

| Role | Model | Why separate |
| --- | --- | --- |
| Answerer (RAG) | `gpt-4.1-1` | Writes the answer + optional inline citations. |
| Synth-GT author | `mistral-large-3` | Writes the gold question + gold answer from a sampled passage. |
| Judge | `llama-3.3-70b-instruct` | Rates faithfulness of the answerer's citations. |

The factory in `src/sentcite/llm.py` asserts at import time that
the three deployments have distinct `model_identity` values. If
someone ever re-points two roles at the same deployment by
accident, the eval harness fails loudly rather than silently
producing self-certifying numbers.

## Self-consistency

A system that gives different citations every time is not
auditable. We re-run each question 5 times at `temperature=0.7`,
with retrieval pinned (the retrieval step is deterministic, so
re-running it would add nothing — only sampling varies). Reported:

- **Stability** (headline) — `|∩| / |∪|` across the 5 citation
  sets. 1.0 means identical every run, 0.0 means no overlap.
- **Mean pairwise Jaccard** — averaged over the C(5, 2) = 10
  pairs. Smoother signal than stability when runs drift
  asymmetrically.
- **Stable anchor IDs** — sentence IDs cited in ≥ ⌈0.5 × N⌉ runs
  (majority threshold). These are the citations a customer will
  see reliably.

## LLM-as-judge faithfulness

For each answer sentence, the judge gets:

- The answer sentence text.
- The text of each cited sentence.
- A short rubric with the three labels (`supported`,
  `partially_supported`, `not_supported`).

The judge does **not** see the question, the gold answer, or
anything else from the answerer's context. This keeps the judge
from rewarding an answerer who cited "close to the right place" —
the only question on the table is "does the cited text back up
this claim in isolation?"

Reported:

- **`percent_faithful`** — percent of answer sentences rated
  `supported`. Headline number.
- **`percent_sentences_any_faithful`** — percent rated
  `supported` **or** `partially_supported`. Useful to separate
  "the citation is wrong" from "the citation is incomplete."

## Resilience under content-filter and API errors

Microsoft Foundry's content safety filter fires unpredictably on
IRS corpus content (we've seen false positives on standard tax
Q&A). The harness has `try/except` at every I/O layer —
`retrieve`, `generate + cite`, `judge`, and `self_consistency`.
Failed items record a zero-score `ItemEval` with the error message
in the `error` field, so a one-item content-filter trip no longer
aborts a 100-item batch.

Two dedicated tests cover the retrieve-failure and generate-
failure recovery paths.

## Layperson review

The Phase-1a bridge between "LLMs self-judging" and "SME
validation." `scripts/review_gt.py` walks a reviewer through a
sampled subset of items. For each item they see:

- Question, gold answer, gold citation IDs, source span.
- Any union additions (sentences the judge flagged as additionally
  supporting).
- The self-judge's reasons for passing the item.

They tag it `high` / `medium` / `low` confidence, optionally
attach flags from a controlled vocabulary (`citation_mismatch`,
`gold_answer_wrong`, `question_unclear`, …) and optionally leave
notes. Written to `reviews.jsonl`.

`run_eval.py --reviews <path>` stitches this into the report,
which grows a new section:

```
### F1 by reviewer confidence (non-SME)

_Layperson (ML Eng / PM) spot-check only. Not a substitute for SME
validation._

| Confidence | inline_prompted | post_gen_alignment |
| --- | --- | --- |
| high | 0.xxx (n=N) | 0.xxx (n=N) |
| medium | ... | ... |
| low | ... | ... |
```

The section is only rendered when at least one item carries a
reviewer tag, so historical unreviewed runs stay unchanged.

{: .important }
> The reviewer-confidence slice **does not** claim tax-law
> accuracy. It's a sanity-check layer against obviously broken
> synth-GT items. The explicit non-SME label ships in every
> output: markdown report, JSONL, and manifest.

## Public-benchmark track

`scripts/run_benchmark.py --format hagrid --input <path>`:

- Loads HAGRID or ALCE JSONL.
- Synthesises a `RetrievalResult` per item from the packaged
  passages (the benchmark already decided the candidate pool).
- Runs both strategies through the same generate + cite path.
- Scores at **passage grain** (which is what HAGRID and ALCE
  annotate).
- Emits the same `EvalReport` shape as the synth-GT harness.

This gives the customer a published-literature comparison point
independent of our synth-GT caveat.
