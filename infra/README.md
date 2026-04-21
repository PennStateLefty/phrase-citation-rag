# Azure Infrastructure

Bicep + deploy script for the sentence-citation-prototype Azure resources.

## What gets provisioned

| Resource | SKU | Notes |
|---|---|---|
| Storage account + `raw-pdfs` / `parsed` containers | Standard_LRS | HTTPS only, public blob access disabled |
| Azure AI Document Intelligence | S0 | Used for the Layout API (structure-aware parse) |
| Azure AI Search | **standard** | Semantic ranker enabled; SKU must be ≥ `standard` so skillsets + **index projections** work for the sentence-child-index spike |
| Azure OpenAI | S0 | `gpt-4o` (GlobalStandard, 50k TPM) + `text-embedding-3-large` (Standard, 100k TPM) |

## Prerequisites

1. `az` CLI installed and logged in (`az login`).
2. A subscription with **Azure OpenAI access** in your target region
   (request via <https://aka.ms/oai/access> if needed).
3. Models available in the region:
   - `gpt-4o` version `2024-08-06`
   - `text-embedding-3-large` version `1`
   If either is unavailable in your region, override the Bicep params:
   `--parameters chatModelVersion=...` etc.

## Deploy

```bash
# optional overrides
export RG=rg-sentcite-dev
export LOCATION=eastus2
export NAME_PREFIX=sentcite

./infra/deploy.sh
```

`deploy.sh` runs the Bicep deployment, then fetches keys and writes the
project-level `.env` (mode 0600). Re-running is safe — any existing
`.env` is backed up with a timestamp.

## Teardown

```bash
az group delete -n "$RG" --yes --no-wait
```

## Not yet configured (deliberately)

- **Entra ID (AAD) auth / managed identity** — Phase 1 uses keys for
  simplicity. Production path is Entra + RBAC (see Phase 2 in the plan).
- **Private networking** — all endpoints are public; demo-only.
- **Content safety / RAI custom policies** — defaults only.
- **Monitoring / Log Analytics** — not wired up.

These are called out in the plan's Phase 2 productionization bullet.
