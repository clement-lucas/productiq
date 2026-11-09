// Log Analytics + workspace-based Application Insights (OpenTelemetry target for Agent Framework and Foundry tracing).
param logAnalyticsName string
param appInsightsName string
param location string
param tags object

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

output logAnalyticsId string = logs.id
output appInsightsId string = appi.id
output appInsightsAppId string = appi.properties.AppId
output appInsightsConnectionString string = appi.properties.ConnectionString
