---
title: Notebooks
layout: default
nav_order: 4
permalink: /notebooks/
---

# Notebooks
{: .no_toc }

<details markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

The repo ships two parallel notebook series. Both are in
[`notebooks/`](https://github.com/PennStateLefty/phrase-citation-rag/tree/main/notebooks)
and both render directly on GitHub.

- **Technical series** (`00` – `05b`) — the real pipeline. Each
  notebook calls live Azure services (Document Intelligence, AI
  Search, Azure OpenAI) and mutates the indexes under
  `rg-phrase-citation-testing`. You need a populated `.env` and the
  provisioned infra to run these.
- **Demo series** (`demo_01` – `demo_03`) — a zero-Azure walkthrough
  for customer screenshares and async reviewers. Every cell reads
  from the committed `data/notebook_cache/` bundle, so a fresh venv
  is the only prerequisite.

## Which series should I read?

| I am… | Read |
| --- | --- |
| An engineer or SE onboarding to the codebase | Technical series top-to-bottom, starting at `00_llm_smoke_test`. |
| Prepping a customer screenshare or internal demo | Demo series (`demo_01` → `demo_02` → `demo_03`). |
| Reviewing the methodology before a deep-dive | The [Phase 1a write-up]({{ '/phase-1a/' | relative_url }}) first, then `05_evaluation` and `05b_public_benchmark` in the technical series. |

## Technical series

Requires Azure (`.env` populated, infra provisioned) and the
`Python (sentcite .venv)` Jupyter kernel.

| # | Notebook | What it does | Azure? | Prereqs |
| --- | --- | --- | --- | --- |
| 00 | [`00_llm_smoke_test.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/00_llm_smoke_test.ipynb) | Confirms Entra-ID auth and the three-role model factory (RAG / synth-GT / judge) talk to Azure OpenAI. | yes | `.env`, venv |
| 01 | [`01_ingest_and_parse.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/01_ingest_and_parse.ipynb) | Pulls IRS PDFs through Azure Document Intelligence into structured JSON under `data/parsed/`. | yes | 00 |
| 02 | [`02_chunk_and_index.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/02_chunk_and_index.ipynb) | Chunks parsed pages with spaCy and builds the dual-layout Azure AI Search indexes (chunks-with-nested-sentences + sentences). | yes | 01 |
| 03 | [`03_query_and_generate.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/03_query_and_generate.ipynb) | Hybrid retrieval + both generation strategies (inline-prompted and post-gen alignment) end-to-end on a sample question. | yes | 02 |
| 04 | [`04_citation_alignment.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/04_citation_alignment.ipynb) | Zooms into the post-gen aligner — cosine thresholds, top-k cap, and per-sentence matching traces. | yes | 03 |
| 05 | [`05_evaluation.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/05_evaluation.ipynb) | Runs `evaluate_gt_set` and walks through P/R/F1, coverage, retrieval R@k, judge faithfulness, and self-consistency. | yes | 03, GT file |
| 05a | [`05a_synthetic_gt.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/05a_synthetic_gt.ipynb) | Generates synthetic ground truth (author → answerer → judge) and applies the well-formedness / supported-by-source gates. | yes | 02 |
| 05b | [`05b_public_benchmark.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/05b_public_benchmark.ipynb) | Runs the HAGRID / ALCE adapter for apples-to-apples passage-grain comparison against published attribution numbers. | yes | 02 |

## Demo series

Requires **only** a Python venv and the committed
`data/notebook_cache/` bundle — no Azure, no `.env`, no network.

| # | Notebook | What it does | Azure? | Prereqs |
| --- | --- | --- | --- | --- |
| 01 | [`demo_01_the_problem.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/demo_01_the_problem.ipynb) | Frames the auditor verification problem with cached examples — why page-level citations aren't enough. | no | venv |
| 02 | [`demo_02_pipeline_tour.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/demo_02_pipeline_tour.ipynb) | Click-through tour of ingest → chunk → retrieve → generate → cite, using cached outputs. The best single notebook for a non-engineer audience. | no | venv |
| 03 | [`demo_03_metrics_that_matter.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/demo_03_metrics_that_matter.ipynb) | Walks the headline metrics (faithfulness, stability, coverage) from cached eval outputs and explains what to quote to a customer. | no | venv |

## Running locally

```bash
# From the repo root, inside the activated project venv:
source .venv/bin/activate
jupyter lab          # or: jupyter notebook
```

In Jupyter, select the **`Python (sentcite .venv)`** kernel, then
open the series you want. The demo series runs as-is. The technical
series additionally needs `.env` populated and the Azure infra from
`infra/` provisioned.

If you want to execute notebooks headlessly (e.g. to regenerate the
smoke-test output) you'll also want the dev extras:

```bash
pip install '.[dev]'   # pulls nbclient, matplotlib, etc.
```

{: .note }
> **Renamed in April 2026.** The old
> `02_chunking.ipynb` is now
> [`02_chunk_and_index.ipynb`](https://github.com/PennStateLefty/phrase-citation-rag/blob/main/notebooks/02_chunk_and_index.ipynb) —
> the notebook now covers both chunking and index construction.
> Update any bookmarks or external links accordingly.
