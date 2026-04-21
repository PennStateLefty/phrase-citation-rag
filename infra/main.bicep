// main.bicep — Azure resources for the sentence-citation-prototype.
//
// Foundry resource model: post-Ignite 2025 ("Microsoft Foundry vNext"), i.e.
// Microsoft.CognitiveServices/accounts kind=AIServices with
// allowProjectManagement=true + an accounts/projects child. This is the
// current GA "Foundry Resource" type per the official Bicep quickstart
// (microsoft-foundry/foundry-samples/infrastructure-setup-bicep/00-basic).
// API version 2025-06-01 (stable).
//
// Provisions:
//   - Storage Account + 2 blob containers (raw-pdfs, parsed)
//   - Azure AI Document Intelligence (Cognitive Services kind=FormRecognizer)
//   - Azure AI Search (standard SKU by default, semantic ranker enabled)
//   - Azure AI Foundry account + project (vNext) with two Azure OpenAI
//     model deployments: gpt-4o + text-embedding-3-large.
//
// Additional Foundry model-catalog models (e.g. Llama-3.3-70B, Mistral
// Large 2, DeepSeek, Phi-4) are NOT deployed here because MaaS model
// availability varies by region and requires Marketplace T&Cs. Deploy
// those interactively from the Foundry portal; see infra/README.md.
//
// No secrets are emitted as outputs. Keys must be fetched via `az` by
// deploy.sh and written to the local .env file.

@description('Location for all resources. Must be a region where Azure OpenAI + the requested models are available.')
param location string = resourceGroup().location

@description('Short prefix for resource names (lowercase letters/digits, 3-11 chars).')
@minLength(3)
@maxLength(11)
param namePrefix string = 'sentcite'

@description('Storage SKU.')
param storageSku string = 'Standard_LRS'

@description('Azure AI Search SKU. "standard" or higher is required for skillsets / index projections.')
@allowed([ 'basic', 'standard', 'standard2', 'standard3' ])
param searchSku string = 'standard'

param searchReplicas int = 1
param searchPartitions int = 1

@description('Foundry / Azure OpenAI SKU.')
param openaiSku string = 'S0'

@description('Name of the Foundry project created under the AI Services account.')
param foundryProjectName string = 'sentcite'

@description('Friendly display name of the Foundry project.')
param foundryProjectDisplayName string = 'Sentence Citation Prototype'

@description('Description of the Foundry project.')
param foundryProjectDescription string = 'Phase 1 prototype for sentence-level citation RAG over public IRS/Treasury corpus.'

@description('Chat deployment model name.')
param chatModel string = 'gpt-4o'

@description('Chat deployment model version.')
param chatModelVersion string = '2024-08-06'

@description('Chat deployment capacity in thousands of tokens per minute (TPM).')
param chatCapacity int = 50

@description('Embedding deployment model name.')
param embeddingModel string = 'text-embedding-3-large'

@description('Embedding deployment model version.')
param embeddingModelVersion string = '1'

@description('Embedding deployment SKU name. GlobalStandard is broadly available; some regions do not offer Standard for text-embedding-3-large.')
@allowed([ 'Standard', 'GlobalStandard' ])
param embeddingSkuName string = 'GlobalStandard'

@description('Embedding deployment capacity (TPM, thousands).')
param embeddingCapacity int = 100

var uniq = uniqueString(resourceGroup().id)
var shortUniq = substring(uniq, 0, 6)
var storageName = take(toLower('${namePrefix}${uniq}'), 24)
var docIntelName = '${namePrefix}-docintel-${shortUniq}'
var searchName = take('${namePrefix}-search-${shortUniq}', 60)
var foundryName = take('${namePrefix}-foundry-${shortUniq}', 60)

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: storageSku }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource rawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'raw-pdfs'
}

resource parsedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'parsed'
}

resource docIntel 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: docIntelName
  location: location
  kind: 'FormRecognizer'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: docIntelName
    publicNetworkAccess: 'Enabled'
  }
}

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchName
  location: location
  sku: { name: searchSku }
  properties: {
    replicaCount: searchReplicas
    partitionCount: searchPartitions
    hostingMode: 'default'
    semanticSearch: 'standard'
  }
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryName
  location: location
  kind: 'AIServices'
  sku: { name: openaiSku }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: foundryName
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
    disableLocalAuth: false
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: foundryProjectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: foundryProjectDisplayName
    description: foundryProjectDescription
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: chatModel
  sku: {
    name: 'GlobalStandard'
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModel
      version: chatModelVersion
    }
    raiPolicyName: 'Microsoft.Default'
  }
}

// Sequential to avoid a 429 on concurrent deployment creation.
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: embeddingModel
  sku: {
    name: embeddingSkuName
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModel
      version: embeddingModelVersion
    }
    raiPolicyName: 'Microsoft.Default'
  }
  dependsOn: [ chatDeployment ]
}

output storageAccountName string = storage.name
output docIntelName string = docIntel.name
output docIntelEndpoint string = docIntel.properties.endpoint
output searchName string = search.name
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output foundryName string = foundry.name
output foundryEndpoint string = foundry.properties.endpoint
output foundryProjectName string = foundryProject.name
// The Foundry project exposes a dictionary of endpoints. The "AI Foundry API"
// key is the unified agent/inference endpoint introduced at Ignite 2025.
output foundryProjectEndpoint string = foundryProject.properties.endpoints['AI Foundry API']
output openaiChatDeployment string = chatDeployment.name
output openaiEmbeddingDeployment string = embeddingDeployment.name
