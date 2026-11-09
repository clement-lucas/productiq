// Azure Cosmos DB for NoSQL (serverless) – sessions, project memory, chat bindings, scorecards, decisions, audit.
param name string
param location string
param tags object
param databaseName string = 'productiq'

var containers = [
  { name: 'sessions', pk: '/userId' }
  { name: 'projects', pk: '/projectId' }
  { name: 'chatBindings', pk: '/chatId' }
  { name: 'memories', pk: '/scopeId' }
  { name: 'scorecards', pk: '/projectId' }
  { name: 'decisions', pk: '/projectId' }
  { name: 'audit', pk: '/projectId' }
]

resource account 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [ { locationName: location, failoverPriority: 0, isZoneRedundant: false } ]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    capabilities: [ { name: 'EnableServerless' } ]
    disableLocalAuth: true               // Entra ID (RBAC) only
    publicNetworkAccess: 'Enabled'
    minimalTlsVersion: 'Tls12'
  }
}

resource db 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: account
  name: databaseName
  properties: { resource: { id: databaseName } }
}

resource cols 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = [for c in containers: {
  parent: db
  name: c.name
  properties: {
    resource: {
      id: c.name
      partitionKey: { paths: [ c.pk ], kind: 'Hash' }
      defaultTtl: c.name == 'sessions' ? 2592000 : -1   // sessions expire after 30 days
    }
  }
}]

output id string = account.id
output name string = account.name
output endpoint string = account.properties.documentEndpoint
output databaseName string = databaseName
