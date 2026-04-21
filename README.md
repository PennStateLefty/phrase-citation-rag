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

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm

# 2. Configure
cp .env.example .env
# fill in Azure endpoints/keys

# 3. Provision Azure resources (see infra/)
# 4. Walk the notebooks in order: 01 → 05
```

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
