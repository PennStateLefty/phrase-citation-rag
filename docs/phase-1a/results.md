---
title: Results
parent: Phase 1a
nav_order: 5
---

# Current results (smoke run)
{: .no_toc }

<details markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

{: .important }
> These numbers are from **5-item smoke runs** against
> **synthetic** ground truth. They are a sanity check that the
> pipeline is internally consistent, not an accuracy claim.
> Customer-facing headline metrics require the SME-authored GT
> that's blocked behind Phase 1b.

## Synthetic GT smoke (5 items, both strategies)

Run: `data/eval/smoke-eval/`
Corpus: IRS Pub 587, Pub 946
Retrieval: `mode=dual, k_sentences=20, k_chunks=5`
Citation: `tau=0.75, top_k=3`
Elapsed: ~4 min (with faithfulness + self-consistency on).

| Metric | inline_prompted | post_gen_alignment |
| --- | --- | --- |
| Precision | 0.275 | 0.000 |
| Recall | 0.313 | 0.000 |
| F1 | 0.270 | 0.000 |
| Coverage | 1.000 | 0.440 |
| Retrieval R@k | 0.760 | 0.760 |
| Faithful % | 83.6 | 43.8 |
| Stability | 0.723 | 0.375 |

### F1 by difficulty

| Difficulty | inline_prompted | post_gen_alignment |
| --- | --- | --- |
| easy (n=3) | 0.229 | 0.000 |
| medium (n=2) | 0.333 | 0.000 |
| hard | n/a | n/a |

## What these numbers are saying

1. **Strategy A (inline prompted) is winning on the honest
   axes.** 83.6% of its answer sentences have a citation the judge
   rates as actually supporting the claim, and 72% of its
   citations survive a 5× re-run at temperature 0.7.

2. **Strategy B (post-gen alignment) has an F1=0.000 problem that
   is mostly a measurement artefact.** The aligner picks parallel
   or adjacent sentences that support the claim — the judge
   agrees 44% of the time — but the synth-GT's set-based F1 gives
   0 credit for "close but not the author's exact sid." See the
   example in
   [evaluation]({{ '/phase-1a/evaluation/#why-f1-against-synth-gt-is-pessimistic' | relative_url }}).

3. **Retrieval is not the bottleneck.** Retrieval R@k = 0.76 on
   both strategies means the right sentences *were* in the
   candidate pool 76% of the time. The citation step is losing
   ground from there, not the retrieval step.

4. **Stability matters for customer trust.** 0.72 on Strategy A
   means ~28% of cited sids changed across re-runs. That's
   tolerable but not great; we should plan to temperature-anneal
   the answerer (or switch to Strategy A + deterministic
   decoding) before the real demo.

5. **Strategy B's low coverage (0.44) is also a signal** — the
   aligner is dropping citations when nothing in the pool passes
   the τ=0.75 threshold. We can trade that off (lower τ →
   more coverage → more false positives).

## Public benchmark smoke (2 items, HAGRID-shape fixture)

Run: `data/eval/smoke-hagrid/`
Corpus: hand-built HAGRID-shape fixture.
Elapsed: 13.9 s.

| Metric | inline_prompted | post_gen_alignment |
| --- | --- | --- |
| Precision | 1.000 | 1.000 |
| Recall | 1.000 | 1.000 |
| F1 | 1.000 | 1.000 |
| Coverage | 1.000 | 1.000 |
| Retrieval R@k | 1.000 | 1.000 |

End-to-end plumbing green against Azure-hosted `gpt-4.1-1`. The
next step on the public-benchmark track is to pull a 50–100-item
slice of real HAGRID dev data and re-run; that work is
unblocked but not yet done because the smoke was sufficient to
validate the adapter.

## How to interpret these for a customer

Lead with:

1. **Faithfulness** (83.6% on Strategy A) — "When our system
   cites a source, the citation is a real fit 84% of the time, as
   judged by an independent third-party language model."
2. **Stability** (0.72) — "Re-running the same question five
   times, 72% of citations are the same every time."
3. **Coverage** (100% on Strategy A) — "Every sentence of every
   answer got at least one citation."
4. **Latency** — single-question eval is ~5 s incl. retrieval
   (faithfulness + stability add more).

Then introduce the F1 numbers **with the pessimism caveat**. If a
customer is technical enough to ask about F1 at all, they're
technical enough to understand why set-based F1 against synth-GT
is a lower bound, not a true accuracy measure.

## What the numbers don't cover yet

- **Tax-law correctness.** Needs SME (Phase 1b).
- **Inter-annotator agreement.** Needs two SMEs (Phase 1b).
- **Hard-tier items.** None of the smoke items landed in the
  `hard` difficulty bucket. The 100-item run (gated on running
  the full eval against the existing 100-item synth-GT set)
  will populate all three tiers.
- **Scale.** 5-item runs are reproducibility smoke, not a
  statistical sample. The 100-item run is a straightforward re-
  launch of the same command; no code changes required.
