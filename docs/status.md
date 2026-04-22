---
title: Status
layout: default
nav_order: 2
---

# Project status
{: .no_toc }

Last updated: 2026-04-22
{: .fs-3 .text-grey-dk-000 }

<details markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## TL;DR

**Phase 1a is complete.** The pipeline works end-to-end on IRS tax
documents, produces sentence-level citations under two competing
strategies, and we have honest measurements of accuracy, faithfulness,
and stability. We are ready to hand the demo to the customer for the
SME-validation conversation that unblocks Phase 1b.

{: .important }
> Headline customer-facing metrics should use **judge-rated
> faithfulness** and **citation stability**, not F1 against synthetic
> ground truth. F1 against synth-GT is too harsh because the aligner
> often cites adjacent / parallel sentences that support the claim but
> aren't the author-model's exact provenance span. See
> [evaluation]({{ '/phase-1a/evaluation/' | relative_url }}) for
> specifics.

## Track status

| Track | Status | Notes |
| --- | --- | --- |
| Repo scaffold | ✅ Done | venv-first layout, Azure SDKs pinned, spaCy kernel registered. |
| Third-party LLM access | ✅ Done | Entra-ID via `DefaultAzureCredential`; three-role factory (RAG / synth-GT / judge). |
| Infra bootstrap | ✅ Done | `rg-phrase-citation-testing` in swedencentral. |
| Ingest + parse | ✅ Done | Azure Document Intelligence Layout API. |
| Chunking | ✅ Done | spaCy sentence boundaries, section-aware chunks. |
| Indexing | ✅ Done | Dual layout (chunks-with-nested-sentences + sentences index). |
| Index projections spike | ✅ Done | Layout comparison captured in [technical notes]({{ '/index-projections-eval/' | relative_url }}). |
| Retrieval | ✅ Done | Hybrid BM25 + vector + semantic reranker. |
| Generation strategies | ✅ Done | Inline-prompted + post-gen-alignment. |
| Citation alignment | ✅ Done | Cosine-similarity aligner with τ threshold + top-k cap. |
| Synthetic GT generator | ✅ Done | `mistral-large-3` author → `gpt-4.1-1` answerer → `llama-3.3-70b` judge. |
| Synthetic GT quality gates | ✅ Done | Well-formedness + supported-by-source checks. |
| Default corpus selection | ✅ Done | IRS Pub 587 + Pub 946 + related. |
| Eval harness | ✅ Done | `evaluate_gt_set` → per-strategy P/R/F1, coverage, retrieval R@k, judge faithfulness, stability. |
| LLM judge | ✅ Done | Separate `llama-3.3-70b-instruct` binding; faithfulness at answer-sentence grain. |
| Self-consistency metric | ✅ Done | Stability = \|∩\| / \|∪\| across N replicas; stable-anchor-sids surfaced. |
| Public-benchmark track | ✅ Done | HAGRID + ALCE loaders, passage-grain scoring, CLI. |
| Layperson review subset | ✅ Done | Interactive CLI, reviewer-confidence bucketing, **non-SME** labelling in reports. |
| Corpus manifest (formal) | ⛔ Blocked on SME | Requires tax SME sign-off on document scope. |
| GT questions (SME-authored) | ⛔ Blocked on SME | |
| GT answers (SME-authored) | ⛔ Blocked on SME | |
| GT citations (SME-authored) | ⛔ Blocked on SME | |
| Inter-annotator agreement | ⛔ Blocked on SME | Needs ≥ 2 SME annotators per item. |
| Failure review | ⛔ Blocked on SME | Post-hoc analysis requires SME verdicts. |
| Demo rehearsal | ⛔ Blocked on SME | Headline metrics in the deck should be SME-validated. |

**Totals:** 18 done • 7 blocked on SME • 0 in progress.

## Test & tooling health

- **175 / 175** tests passing.
- Smoke runs against live Azure endpoints reproduce the F1 /
  faithfulness / stability numbers published in
  [results]({{ '/phase-1a/results/' | relative_url }}).
- CI is single-target `pytest` inside the project venv.

## What ships with Phase 1a

1. A reproducible RAG pipeline over the committed IRS corpus.
2. Scripts: `run_eval.py`, `run_benchmark.py`, `review_gt.py`, plus the
   per-component CLIs that produced the demo data.
3. A customer-deck-ready markdown summary that the eval harness emits
   automatically.
4. This documentation site.

## What Phase 1b needs to unlock

Everything in the "blocked on SME" list above. The minimum unblock is:

- **One SME** (tax attorney, CPA, or enrolled agent with relevant
  experience) available for ~1–2 hours per batch of 10–20 items, plus
  a kickoff call on corpus scope.
- **A PM facilitator** to run the labelling session and capture IAA
  data.
- Agreement on which document set counts as the Phase 1b "gold corpus"
  (see [corpus manifest]({{ '/phase-1a/pipeline/#corpus' | relative_url }})
  for the Phase 1a candidate set).

Once SME output arrives, the synth-GT → SME-GT swap is mechanical:
`evaluate_gt_set` takes whichever list of `GroundTruthItem`s you hand
it, and the layperson reviewer bucket becomes a redundant sanity check
rather than the primary story.

## Roadmap

### Phase 1b — SME-validated accuracy story

- SME-authored questions (~50–100 items, stratified by difficulty).
- Dual-SME annotation on a subset for inter-annotator agreement.
- Headline F1 / faithfulness numbers against SME-GT.
- Customer-facing failure review: "here are the 5 worst items and
  what went wrong on each."
- Demo rehearsal with the real numbers.

### Phase 2 — Agentic lift

- Multi-turn retrieval (the auditor asks a follow-up, the system keeps
  context).
- Tool use: pulling a specific citation's page image on demand.
- Auto-research flows referenced in the original research folder —
  out of scope for Phase 1 but explicitly scaffolded for later.

### Phase 3 — Productisation

- Auth + tenancy.
- Audit trail of reviewer decisions.
- Integration with the customer's existing case-management system.
