// Storage account: "knowledge" container feeds Foundry IQ (Azure AI Search blob knowledge source);
// "raw-landing" is an optional landing zone for files before they are loaded to OneLake.
param name string
param location string
param tags object

resource sa 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false          // Entra ID only
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: sa
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for c in [ 'knowledge', 'raw-landing' ]: {
  parent: blob
  name: c
  properties: { publicAccess: 'None' }
}]

output id string = sa.id
output name string = sa.name
output blobEndpoint string = sa.properties.primaryEndpoints.blob
