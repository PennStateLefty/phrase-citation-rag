# Sentence-Level Citation RAG Prototype

A Phase-1 prototype that demonstrates **sentence-level citations** for a RAG
pipeline over public IRS/Treasury tax documents. Intended audience: tax
auditors who need to verify AI-generated answers against specific source
sentences before signing off.

See the implementation plan in
`../.copilot/session-state/.../plan.md` for scope, roles, and the human-
in-the-loop steps.

## Stack

- **Azure AI Document Intelligence** (Layout API) — structured parse of PDFs
- **Azure AI Search** — hybrid BM25 + vector + semantic reranker; index
  projections under evaluation for a child sentence index
- **Azure OpenAI** — `gpt-4o` for generation, `text-embedding-3-large`
  for embeddings
- **spaCy** — sentence boundary detection
- **Python 3.11+**, Jupyter notebooks for the walkthrough

## Quick start

**This project is venv-first.** All Python commands (`pytest`, `jupyter`,
`python -m sentcite.*`, notebook kernels) must run inside `./.venv`.
Never `pip install` into a global/system Python.

```bash
# 1. One-shot bootstrap: creates .venv, installs sentcite + dev extras,
#    downloads the spaCy model, and registers a Jupyter kernel named
#    "Python (sentcite .venv)".
./scripts/bootstrap.sh

# 2. Activate before running anything
source .venv/bin/activate

# 3. Configure Azure
cp .env.example .env
# fill in Azure endpoints/keys

# 4. Provision Azure resources (see infra/)
# 5. Walk the notebooks in order: 01 → 05
#    In Jupyter, select the "Python (sentcite .venv)" kernel.
```

### Verifying the venv is active

```bash
which python   # should print .../sentence-citation-prototype/.venv/bin/python
pytest         # should collect tests from ./tests
```

If `which python` does not point into `.venv`, stop and re-run
`source .venv/bin/activate` — running commands against the system
Python will produce confusing "module not found" errors and may pollute
your global packages.

## Repo layout

```
infra/              Bicep + deploy scripts for Azure resources
src/sentcite/       Python package (ingest, chunking, indexing, retrieval,
                    generate, cite_align, eval, schema)
notebooks/          01_ingest_and_parse … 05_evaluation
data/               raw_pdfs, parsed, chunks, ground_truth (gitignored)
tests/              pytest suite
docs/               design notes, failure-mode reviews, index-projection eval
research/           upstream Copilot Researcher outputs (reference only)
```

## Two citation strategies (compared side-by-side in eval)

- **Strategy A — Inline-prompted:** GPT-4o emits `[s_<sentence_id>]` tags
  inline, parsed and validated post-hoc.
- **Strategy B — Post-generation alignment:** answer sentences embedded and
  cosine-matched against source sentences (threshold τ = 0.75).

## Status

Phase 1 scaffold. See the session plan for the full todo list.
