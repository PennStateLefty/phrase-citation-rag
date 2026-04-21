# Azure Infrastructure

Bicep + deploy script for the sentence-citation-prototype Azure resources.

## What gets provisioned

| Resource | Bicep kind | Notes |
|---|---|---|
| Storage account + `raw-pdfs` / `parsed` containers | `Microsoft.Storage/storageAccounts` | Standard_LRS, HTTPS-only, public blob access disabled |
| Azure AI Document Intelligence | `Microsoft.CognitiveServices kind=FormRecognizer` | S0, used for the Layout API |
| Azure AI Search | `Microsoft.Search/searchServices` | **standard** SKU (required for skillsets / **index projections**) with semantic ranker |
| **Azure AI Foundry account** | `Microsoft.CognitiveServices kind=AIServices` | `allowProjectManagement=true`, system-assigned MI. Serves the Azure OpenAI deployments *and* acts as the Foundry project host. |
| Foundry Project | `Microsoft.CognitiveServices/accounts/projects` | Gives portal access to the Model Catalog for click-deploying non-OpenAI-family models. |
| OpenAI deployment: `gpt-4o` | child of Foundry account | GlobalStandard, 50k TPM. RAG generator role. |
| OpenAI deployment: `text-embedding-3-large` | child of Foundry account | Standard, 100k TPM. |

## Prerequisites

1. `az` CLI installed and logged in (`az login`).
2. Subscription with **Azure OpenAI access** in the target region (request
   via <https://aka.ms/oai/access> if needed).
3. Models available in the region:
   - `gpt-4o` version `2024-08-06`
   - `text-embedding-3-large` version `1`
   Override via `--parameters` if your region differs.

### Subscription policies note

Some subscriptions (e.g. MSIT-managed subs) attach policies that mutate
new Cognitive Services deployments — most notably forcing
`disableLocalAuth=true`, which silently breaks API-key auth for
Phase 1a. `deploy.sh` tags the resource group with `SecurityControl=Ignore`
by default; add any additional bypass tags your subscription needs via
the `RG_TAGS` env var:

```bash
RG_TAGS="SecurityControl=Ignore OtherControl=Ignore" ./infra/deploy.sh
```

## Deploy

```bash
# Defaults:
#   RG=rg-phrase-citation-testing
#   LOCATION=swedencentral
#   NAME_PREFIX=sentcite
#   RG_TAGS=SecurityControl=Ignore   (subscription-policy bypass)
./infra/deploy.sh --region southcentralus
```

`deploy.sh` creates the RG if needed, runs the Bicep deployment, fetches
keys, and writes a mode-0600 `.env`. Re-running is safe (any existing
`.env` is backed up with a timestamp).

## Post-deploy — provision the other two model identities

Phase 1a evaluation requires **three distinct model identities** to avoid
same-family contamination: RAG generator, synth-GT author, and judge.
The Bicep deploys only the OpenAI-family deployments for the RAG role
because Foundry Model Catalog MaaS availability varies by region and
requires Marketplace T&Cs acceptance per model.

To provision the remaining two identities:

1. Open <https://ai.azure.com/>.
2. Select the `sentcite` Foundry project created by the deployment.
3. **Model catalog** → pick a non-OpenAI-family model for the synth-GT
   author role (recommended: `Meta-Llama-3.3-70B-Instruct`, `Mistral-Large-2411`).
   Accept the Marketplace agreement → deploy as a "Serverless API"
   (MaaS) endpoint.
4. Repeat for the judge role with a **different** family
   (recommended: `DeepSeek-V3`, `Phi-4`, or `Cohere-command-r-plus-08-2024`).
5. Copy each deployment's endpoint URL, primary key, deployment name,
   and model name into the corresponding `FOUNDRY_SYNTH_GT_*` and
   `FOUNDRY_JUDGE_*` keys in `.env`.

`sentcite.config.AzureConfig.assert_three_distinct_models()` enforces
the invariant at runtime; `synth_gt.py` and `judge.py` call it on import
so a violation fails loudly instead of producing contaminated metrics.

## Teardown

```bash
az group delete -n "$RG" --yes --no-wait
```

## Not yet configured (deliberately)

- **Entra ID / managed identity auth** — Phase 1 uses keys. Production
  path is Entra + RBAC (Phase 2 in the plan). The Foundry account has
  a system-assigned identity ready for that transition.
- **Private networking** — all endpoints are public; demo-only.
- **Content safety / RAI custom policies** — defaults only.
- **Monitoring / Log Analytics** — not wired up.
