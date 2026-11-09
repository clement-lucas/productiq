// Microsoft Foundry: Foundry resource (Microsoft.CognitiveServices/accounts kind AIServices) + project,
// model deployments and project connections (App Insights, AI Search, Storage, Cosmos DB, Bing grounding).
// Agent setup: BASIC (Microsoft-managed thread/file storage) for the lab. See docs/ARCHITECTURE.md for the
// standard (bring-your-own Cosmos/Storage/Search + VNet) hardening path.
param accountName string
param projectName string
param location string
param tags object
param modelSkuName string = 'GlobalStandard'

@description('Array of { name, model, version, capacity }. version may be empty (service default).')
param deployments array

param appInsightsId string
@secure()
param appInsightsConnectionString string
param searchId string
param searchEndpoint string
param storageId string
param storageBlobEndpoint string
param cosmosId string
param cosmosEndpoint string
@description('Resource ID of the Grounding with Bing Search resource; empty = no Bing connection.')
param bingId string = ''

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true          // Foundry resource (projects as child resources)
    customSubDomainName: accountName      // required for Entra ID auth and the project endpoint
    disableLocalAuth: true                // keyless: Entra ID only
    publicNetworkAccess: 'Enabled'        // lab default – see hardening guide for private networking
    networkAcls: { defaultAction: 'Allow' }
  }
}

@batchSize(1)  // deployments on one account must be created one at a time
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [for d in deployments: {
  parent: account
  name: d.name
  sku: { name: modelSkuName, capacity: d.capacity }
  properties: {
    model: union({ format: 'OpenAI', name: d.model }, empty(d.version) ? {} : { version: d.version })
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}]

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'ProductIQ'
    description: 'ProductIQ – agentic product-innovation copilot (Hack to Build 2026, synthetic Contoso data)'
  }
  dependsOn: [ modelDeployments ]
}

// ---------------- Project connections ----------------
resource connAppInsights 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'appinsights'
  properties: {
    category: 'AppInsights'
    target: appInsightsId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: { key: appInsightsConnectionString }
    metadata: { ApiType: 'Azure', ResourceId: appInsightsId }
  }
}

resource connSearch 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'aisearch'
  properties: {
    category: 'CognitiveSearch'
    target: searchEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: { ApiType: 'Azure', ResourceId: searchId, location: location }
  }
}

resource connStorage 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'storage'
  properties: {
    category: 'AzureStorageAccount'
    target: storageBlobEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: { ApiType: 'Azure', ResourceId: storageId, location: location }
  }
}

resource connCosmos 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'cosmos'
  properties: {
    category: 'CosmosDB'
    target: cosmosEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: { ApiType: 'Azure', ResourceId: cosmosId, location: location }
  }
}

resource bing 'Microsoft.Bing/accounts@2020-06-10' existing = {
  name: empty(bingId) ? 'none' : last(split(bingId, '/'))
}

resource connBing 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (!empty(bingId)) {
  parent: project
  name: 'bing-grounding'
  properties: {
    category: 'GroundingWithBingSearch'
    target: 'https://api.bing.microsoft.com/'
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: { key: bing.listKeys().key1 }
    metadata: { ApiType: 'Azure', ResourceId: bingId, type: 'bing_grounding' }
  }
}

output accountName string = account.name
output accountId string = account.id
output accountPrincipalId string = account.identity.principalId
output projectName string = project.name
output projectId string = project.id
output projectPrincipalId string = project.identity.principalId
output projectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${project.name}'
output openAiEndpoint string = 'https://${account.name}.openai.azure.com/'
