// Key Vault (RBAC authorisation, soft delete, optional purge protection). Holds the Graph app secret and any future secrets.
param name string
param location string
param tags object

@description('Purge protection blocks re-creating a vault with the same name for the retention period after deletion. Off for the lab, ON for production.')
param enablePurgeProtection bool = false

@description('Name of the secret to create (optional).')
param secretName string = 'graph-app-client-secret'

@secure()
@description('Secret value. Empty = no secret is created.')
param secretValue string = ''

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: enablePurgeProtection ? true : null
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

resource kvSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(secretValue)) {
  parent: kv
  name: secretName
  properties: { value: secretValue }
}

output id string = kv.id
output name string = kv.name
output uri string = kv.properties.vaultUri
