// Azure Container Registry + Container Apps environment + the ProductIQ API app
// (serves /api/messages for Teams / Microsoft 365 Copilot via Azure Bot Service and /api/ask for the web app).
// Starts with a public placeholder image; scripts/11-deploy-app.ps1 builds and rolls out the real image.
param acrName string
param environmentName string
param appName string
param location string
param tags object
param logAnalyticsName string
param identityId string
param identityClientId string
param identityPrincipalId string
@description('Array of { name, value } environment variables for the app container.')
param env array
param placeholderImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsName
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
  }
}

// AcrPull for the app identity (pull images without secrets)
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, identityPrincipalId, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80             // placeholder image port; the deploy script switches to 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [ { server: acr.properties.loginServer, identity: identityId } ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: placeholderImage
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: concat(env, [ { name: 'PORT', value: '8000' } ])
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
  dependsOn: [ acrPull ]
}

output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output appName string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
output identityClientId string = identityClientId
