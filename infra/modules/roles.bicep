// Role assignments (least privilege, keyless). Role IDs are built-in Azure role definition GUIDs.
param deployerPrincipalId string
param deployerPrincipalType string = 'User'
param appPrincipalId string
param searchPrincipalId string
param projectPrincipalId string
param foundryAccountPrincipalId string
param foundryAccountName string
param searchName string
param storageName string
param keyVaultName string
param cosmosName string

var role = {
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'            // Azure AI User (Foundry User)
  azureAiProjectManager: 'eadc314b-1a2d-4efa-be10-5d325db5065e'  // Azure AI Project Manager (Foundry Project Manager)
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  cognitiveServicesOpenAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
  keyVaultSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = { name: foundryAccountName }
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = { name: searchName }
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageName }
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = { name: keyVaultName }
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = { name: cosmosName }

// ---------- Foundry account scope ----------
var foundryAssignments = [
  { p: deployerPrincipalId, t: deployerPrincipalType, r: role.azureAiUser }
  { p: deployerPrincipalId, t: deployerPrincipalType, r: role.azureAiProjectManager }
  { p: appPrincipalId, t: 'ServicePrincipal', r: role.azureAiUser }
  { p: searchPrincipalId, t: 'ServicePrincipal', r: role.cognitiveServicesUser }       // knowledge source embeddings / ingestion
  { p: searchPrincipalId, t: 'ServicePrincipal', r: role.cognitiveServicesOpenAiUser }
  { p: projectPrincipalId, t: 'ServicePrincipal', r: role.azureAiUser }
]
resource foundryRa 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for a in foundryAssignments: {
  scope: foundry
  name: guid(foundry.id, a.p, a.r)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', a.r)
    principalId: a.p
    principalType: a.t
  }
}]

// ---------- Azure AI Search scope ----------
var searchAssignments = [
  { p: deployerPrincipalId, t: deployerPrincipalType, r: role.searchServiceContributor }
  { p: deployerPrincipalId, t: deployerPrincipalType, r: role.searchIndexDataContributor }
  { p: projectPrincipalId, t: 'ServicePrincipal', r: role.searchIndexDataReader }          // Foundry IQ / knowledge base MCP
  { p: projectPrincipalId, t: 'ServicePrincipal', r: role.searchServiceContributor }
  { p: foundryAccountPrincipalId, t: 'ServicePrincipal', r: role.searchIndexDataReader }
  { p: appPrincipalId, t: 'ServicePrincipal', r: role.searchIndexDataReader }
]
resource searchRa 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for a in searchAssignments: {
  scope: search
  name: guid(search.id, a.p, a.r)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', a.r)
    principalId: a.p
    principalType: a.t
  }
}]

// ---------- Storage scope ----------
var storageAssignments = [
  { p: deployerPrincipalId, t: deployerPrincipalType, r: role.storageBlobDataContributor }  // upload knowledge docs
  { p: searchPrincipalId, t: 'ServicePrincipal', r: role.storageBlobDataReader }            // blob knowledge source
  { p: projectPrincipalId, t: 'ServicePrincipal', r: role.storageBlobDataContributor }
  { p: appPrincipalId, t: 'ServicePrincipal', r: role.storageBlobDataReader }
]
resource storageRa 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for a in storageAssignments: {
  scope: storage
  name: guid(storage.id, a.p, a.r)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', a.r)
    principalId: a.p
    principalType: a.t
  }
}]

// ---------- Key Vault scope ----------
var kvAssignments = [
  { p: deployerPrincipalId, t: deployerPrincipalType, r: role.keyVaultSecretsOfficer }
  { p: appPrincipalId, t: 'ServicePrincipal', r: role.keyVaultSecretsUser }
]
resource kvRa 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for a in kvAssignments: {
  scope: kv
  name: guid(kv.id, a.p, a.r)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', a.r)
    principalId: a.p
    principalType: a.t
  }
}]

// ---------- Cosmos DB data plane (built-in "Cosmos DB Built-in Data Contributor") ----------
var cosmosDataContributor = '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
resource cosmosRa 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = [for p in [ appPrincipalId, deployerPrincipalId, projectPrincipalId ]: {
  parent: cosmos
  name: guid(cosmos.id, p, 'data-contributor')
  properties: {
    roleDefinitionId: cosmosDataContributor
    principalId: p
    scope: cosmos.id
  }
}]
