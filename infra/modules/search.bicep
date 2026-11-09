// Azure AI Search – the engine under Foundry IQ knowledge bases (agentic retrieval). Semantic ranker on.
param name string
param location string
param sku string = 'basic'
param tags object

resource srch 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: { name: sku }
  identity: { type: 'SystemAssigned' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: 'free'
    publicNetworkAccess: 'enabled'
    disableLocalAuth: false
    authOptions: { aadOrApiKey: { aadAuthFailureMode: 'http401WithBearerChallenge' } }
  }
}

output id string = srch.id
output name string = srch.name
output endpoint string = 'https://${srch.name}.search.windows.net'
output principalId string = srch.identity.principalId
