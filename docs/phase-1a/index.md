---
title: Phase 1a
layout: default
nav_order: 3
has_children: true
permalink: /phase-1a/
---

# Phase 1a — the foundation

Phase 1a is the "can we build it, and does it measure up to its own
specs?" phase. We did **not** try to answer "is this tax-law
accurate?" here — that requires a subject-matter expert (SME) and is
the explicit scope of Phase 1b.

## What we built in Phase 1a

1. An end-to-end RAG pipeline with **two competing citation
   strategies** so we can show the customer which approach wins, and
   on what axis.
2. A **self-evaluating** pipeline — it generates its own synthetic
   ground truth, judges its own faithfulness with a separate model,
   and measures how stable its citations are under re-sampling.
3. A **benchmark adapter** so numbers on our internal dataset can be
   compared against public attribution benchmarks (HAGRID, ALCE).
4. A **non-SME reviewer workflow** so obvious breakage in the
   synthetic ground truth gets flagged before it reaches a customer
   deck.

## How to read these pages

- [Overview]({{ '/phase-1a/overview/' | relative_url }}) — plain-language
  summary of what the pipeline does, end to end.
- [Concepts]({{ '/phase-1a/concepts/' | relative_url }}) — a glossary
  that explains citation, faithfulness, stability, etc. without
  assuming AI/ML background.
- [Pipeline]({{ '/phase-1a/pipeline/' | relative_url }}) — the
  technical walk-through: ingest → chunk → index → retrieve →
  generate → cite.
- [Evaluation]({{ '/phase-1a/evaluation/' | relative_url }}) — how we
  measure the pipeline, and what each metric means.
- [Results]({{ '/phase-1a/results/' | relative_url }}) — what the
  numbers currently look like on the smoke runs, and how to
  interpret them.
