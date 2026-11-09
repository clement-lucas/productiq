// =============================================================================
// ProductIQ – Azure landing zone for the Hack to Build 2026 lab (single tenant)
// Scope: subscription. Creates one resource group and all Azure resources.
// Compile to ARM:  az bicep build --file infra/main.bicep --outfile infra/arm/azuredeploy.json
// Deploy:          scripts/03-deploy-infra.ps1  (wraps az deployment sub create)
// =============================================================================
targetScope = 'subscription'

@description('Short environment name, e.g. dev, test, prod.')
@maxLength(8)
param environmentName string = 'dev'

@description('Resource name prefix (3-5 lowercase letters).')
@minLength(2)
@maxLength(5)
param prefix string = 'piq'

@description('Azure region for all regional resources. Keep Foundry and the Fabric capacity in the same region where possible.')
param location string = 'eastus2'

@description('Object ID of the user or service principal running the deployment (gets data-plane roles for setup scripts).')
param deployerPrincipalId string

@allowed([ 'User', 'ServicePrincipal' ])
param deployerPrincipalType string = 'User'

@description('Entra tenant ID (used by Bot Service).')
param tenantId string = subscription().tenantId

// ---------- Microsoft Fabric ----------
@description('Deploy a Fabric capacity (F SKU). Pause it when not in use to save cost.')
param deployFabricCapacity bool = true

@allowed([ 'F2', 'F4', 'F8', 'F16', 'F32', 'F64' ])
param fabricSku string = 'F2'

@description('UPNs (or object IDs) of Fabric capacity administrators.')
param fabricAdminMembers array = []

// ---------- Foundry models ----------
@description('Reasoning / synthesis model (Product Strategist, Concept Designer).')
param reasoningModelName string = 'gpt-5.4'
@description('Leave empty to use the default model version.')
param reasoningModelVersion string = ''
param reasoningModelCapacity int = 50

@description('Smaller model for specialists and routing.')
param routerModelName string = 'gpt-5.4-mini'
param routerModelVersion string = ''
param routerModelCapacity int = 100

param embeddingModelName string = 'text-embedding-3-large'
param embeddingModelVersion string = '1'
param embeddingModelCapacity int = 50

@description('Model deployment SKU. GlobalStandard has the widest availability.')
param modelSkuName string = 'GlobalStandard'

// ---------- Optional features ----------
@description('Create Grounding with Bing Search and its Foundry connection (data leaves the Azure compliance boundary – see docs/SECURITY.md).')
param enableBingGrounding bool = true

@description('Azure AI Search SKU (basic is enough for the lab; agentic retrieval needs semantic ranker).')
@allowed([ 'basic', 'standard', 'standard2' ])
param searchSku string = 'basic'

// ---------- Teams / M365 bot ----------
@description('Client ID of the Entra app "ProductIQ-Graph" used for delegated Graph calls (from scripts/02-setup-entra.ps1). Empty = skip the bot OAuth connection.')
param graphAppClientId string = ''

@secure()
@description('Client secret of the "ProductIQ-Graph" app. Stored in Key Vault and in the Bot OAuth connection.')
param graphAppClientSecret string = ''

@description('Bot Service pricing tier (F0 free is fine for the lab).')
@allowed([ 'F0', 'S1' ])
param botSku string = 'F0'

param tags object = {}

// -----------------------------------------------------------------------------
var token = toLower(uniqueString(subscription().id, environmentName, location, prefix))
var short = take(token, 6)
var baseTags = union({
  workload: 'productiq'
  environment: environmentName
  programme: 'hack-to-build-2026'
  'data-classification': 'synthetic-demo'
}, tags)

var names = {
  rg: 'rg-${prefix}-${environmentName}'
  identity: 'id-${prefix}-app-${environmentName}'
  logs: 'log-${prefix}-${environmentName}-${short}'
  appi: 'appi-${prefix}-${environmentName}-${short}'
  kv: take('kv-${prefix}-${environmentName}-${short}', 24)
  storage: take(toLower('st${prefix}${environmentName}${token}'), 24)
  cosmos: take('cosmos-${prefix}-${environmentName}-${short}', 44)
  search: 'srch-${prefix}-${environmentName}-${short}'
  foundry: take('ais-${prefix}-${environmentName}-${short}', 64)
  project: 'proj-${prefix}-${environmentName}'
  bing: 'bing-${prefix}-${environmentName}-${short}'
  acr: take(toLower('cr${prefix}${environmentName}${token}'), 50)
  cae: 'cae-${prefix}-${environmentName}'
  app: 'ca-${prefix}-api-${environmentName}'
  bot: 'bot-${prefix}-${environmentName}-${short}'
  fabric: take(toLower('fc${prefix}${environmentName}${short}'), 63)
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: names.rg
  location: location
  tags: baseTags
}

module identity 'modules/identity.bicep' = {
  scope: rg
  name: 'identity'
  params: { name: names.identity, location: location, tags: baseTags }
}

module monitoring 'modules/monitoring.bicep' = {
  scope: rg
  name: 'monitoring'
  params: { logAnalyticsName: names.logs, appInsightsName: names.appi, location: location, tags: baseTags }
}

module keyVault 'modules/keyvault.bicep' = {
  scope: rg
  name: 'keyvault'
  params: {
    name: names.kv
    location: location
    tags: baseTags
    secretName: 'graph-app-client-secret'
    secretValue: graphAppClientSecret
  }
}

module storage 'modules/storage.bicep' = {
  scope: rg
  name: 'storage'
  params: { name: names.storage, location: location, tags: baseTags }
}

module cosmos 'modules/cosmos.bicep' = {
  scope: rg
  name: 'cosmos'
  params: { name: names.cosmos, location: location, tags: baseTags }
}

module search 'modules/search.bicep' = {
  scope: rg
  name: 'search'
  params: { name: names.search, location: location, sku: searchSku, tags: baseTags }
}

module bing 'modules/bing.bicep' = if (enableBingGrounding) {
  scope: rg
  name: 'bing'
  params: { name: names.bing, tags: baseTags }
}

module foundry 'modules/foundry.bicep' = {
  scope: rg
  name: 'foundry'
  params: {
    accountName: names.foundry
    projectName: names.project
    location: location
    tags: baseTags
    modelSkuName: modelSkuName
    deployments: [
      { name: reasoningModelName, model: reasoningModelName, version: reasoningModelVersion, capacity: reasoningModelCapacity }
      { name: routerModelName, model: routerModelName, version: routerModelVersion, capacity: routerModelCapacity }
      { name: embeddingModelName, model: embeddingModelName, version: embeddingModelVersion, capacity: embeddingModelCapacity }
    ]
    appInsightsId: monitoring.outputs.appInsightsId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    searchId: search.outputs.id
    searchEndpoint: search.outputs.endpoint
    storageId: storage.outputs.id
    storageBlobEndpoint: storage.outputs.blobEndpoint
    cosmosId: cosmos.outputs.id
    cosmosEndpoint: cosmos.outputs.endpoint
    bingId: enableBingGrounding ? bing.outputs.id : ''
  }
}

module containerApps 'modules/containerapps.bicep' = {
  scope: rg
  name: 'containerapps'
  params: {
    acrName: names.acr
    environmentName: names.cae
    appName: names.app
    location: location
    tags: baseTags
    logAnalyticsName: names.logs
    identityId: identity.outputs.id
    identityClientId: identity.outputs.clientId
    identityPrincipalId: identity.outputs.principalId
    env: [
      { name: 'AZURE_CLIENT_ID', value: identity.outputs.clientId }
      { name: 'AZURE_TENANT_ID', value: tenantId }
      { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundry.outputs.projectEndpoint }
      { name: 'FOUNDRY_OPENAI_ENDPOINT', value: foundry.outputs.openAiEndpoint }
      { name: 'MODEL_REASONING_DEPLOYMENT', value: reasoningModelName }
      { name: 'MODEL_ROUTER_DEPLOYMENT', value: routerModelName }
      { name: 'MODEL_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
      { name: 'SEARCH_ENDPOINT', value: search.outputs.endpoint }
      { name: 'SEARCH_KNOWLEDGE_BASE', value: 'productiq-kb' }
      { name: 'COSMOS_ENDPOINT', value: cosmos.outputs.endpoint }
      { name: 'COSMOS_DATABASE', value: cosmos.outputs.databaseName }
      { name: 'KEY_VAULT_URI', value: keyVault.outputs.uri }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitoring.outputs.appInsightsConnectionString }
      { name: 'BOT_APP_ID', value: identity.outputs.clientId }
      { name: 'BOT_APP_TENANT_ID', value: tenantId }
      { name: 'BOT_OAUTH_CONNECTION_NAME', value: 'graph-sso' }
      { name: 'GRAPH_APP_CLIENT_ID', value: graphAppClientId }
    ]
  }
  dependsOn: [ monitoring ]
}

module bot 'modules/botservice.bicep' = {
  scope: rg
  name: 'botservice'
  params: {
    name: names.bot
    tags: baseTags
    sku: botSku
    endpoint: 'https://${containerApps.outputs.fqdn}/api/messages'
    msaAppId: identity.outputs.clientId
    msaAppMsiResourceId: identity.outputs.id
    tenantId: tenantId
    appInsightsAppId: monitoring.outputs.appInsightsAppId
    graphAppClientId: graphAppClientId
    graphAppClientSecret: graphAppClientSecret
  }
}

module fabric 'modules/fabric.bicep' = if (deployFabricCapacity) {
  scope: rg
  name: 'fabric'
  params: {
    name: names.fabric
    location: location
    sku: fabricSku
    adminMembers: fabricAdminMembers
    tags: baseTags
  }
}

module roles 'modules/roles.bicep' = {
  scope: rg
  name: 'roles'
  params: {
    deployerPrincipalId: deployerPrincipalId
    deployerPrincipalType: deployerPrincipalType
    appPrincipalId: identity.outputs.principalId
    searchPrincipalId: search.outputs.principalId
    projectPrincipalId: foundry.outputs.projectPrincipalId
    foundryAccountPrincipalId: foundry.outputs.accountPrincipalId
    foundryAccountName: foundry.outputs.accountName
    searchName: search.outputs.name
    storageName: storage.outputs.name
    keyVaultName: keyVault.outputs.name
    cosmosName: cosmos.outputs.name
  }
}

// ---------- Outputs (written to .env by scripts/03-deploy-infra.ps1) ----------
output AZURE_TENANT_ID string = tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_LOCATION string = location
output FOUNDRY_ACCOUNT_NAME string = foundry.outputs.accountName
output FOUNDRY_PROJECT_NAME string = foundry.outputs.projectName
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output FOUNDRY_OPENAI_ENDPOINT string = foundry.outputs.openAiEndpoint
output MODEL_REASONING_DEPLOYMENT string = reasoningModelName
output MODEL_ROUTER_DEPLOYMENT string = routerModelName
output MODEL_EMBEDDING_DEPLOYMENT string = embeddingModelName
output SEARCH_ENDPOINT string = search.outputs.endpoint
output SEARCH_SERVICE_NAME string = search.outputs.name
output STORAGE_ACCOUNT_NAME string = storage.outputs.name
output STORAGE_ACCOUNT_ID string = storage.outputs.id
output COSMOS_ENDPOINT string = cosmos.outputs.endpoint
output COSMOS_DATABASE string = cosmos.outputs.databaseName
output KEY_VAULT_URI string = keyVault.outputs.uri
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString
output ACR_NAME string = containerApps.outputs.acrName
output ACR_LOGIN_SERVER string = containerApps.outputs.acrLoginServer
output CONTAINER_APP_NAME string = containerApps.outputs.appName
output CONTAINER_APP_FQDN string = containerApps.outputs.fqdn
output BOT_NAME string = bot.outputs.name
output BOT_APP_ID string = identity.outputs.clientId
output APP_PRINCIPAL_ID string = identity.outputs.principalId
output BOT_APP_TENANT_ID string = tenantId
output BOT_MSI_RESOURCE_ID string = identity.outputs.id
output BOT_OAUTH_CONNECTION_NAME string = 'graph-sso'
output GRAPH_APP_CLIENT_ID string = graphAppClientId
output FABRIC_CAPACITY_NAME string = deployFabricCapacity ? fabric.outputs.name : ''
output FABRIC_CAPACITY_ID string = deployFabricCapacity ? fabric.outputs.id : ''
output BING_CONNECTION_NAME string = enableBingGrounding ? 'bing-grounding' : ''
