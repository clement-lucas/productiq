// Azure Bot Service – channel for Microsoft Teams and Microsoft 365 Copilot (custom engine agent).
// Bot identity = user-assigned managed identity (msaAppType UserAssignedMSI): no bot password to manage.
// OAuth connection "graph-sso" lets the Collaboration Agent call Microsoft Graph with the user's delegated token.
param name string
param tags object
param sku string = 'F0'
param endpoint string
param msaAppId string
param msaAppMsiResourceId string
param tenantId string
param appInsightsAppId string = ''
param graphAppClientId string = ''
@secure()
param graphAppClientSecret string = ''
@description('Delegated Graph scopes requested by the OAuth connection (space separated).')
param graphScopes string = 'openid profile offline_access User.Read Calendars.ReadWrite OnlineMeetings.ReadWrite Chat.Create Chat.ReadWrite ChatMessage.Send TeamsAppInstallation.ReadWriteForChat People.Read'

resource bot 'Microsoft.BotService/botServices@2022-09-15' = {
  name: name
  location: 'global'
  tags: tags
  kind: 'azurebot'
  sku: { name: sku }
  properties: {
    displayName: 'ProductIQ'
    description: 'ProductIQ – product-innovation copilot (Contoso Home Appliances demo, synthetic data)'
    endpoint: endpoint
    msaAppId: msaAppId
    msaAppType: 'UserAssignedMSI'
    msaAppMSIResourceId: msaAppMsiResourceId
    msaAppTenantId: tenantId
    developerAppInsightsApplicationId: empty(appInsightsAppId) ? null : appInsightsAppId
    disableLocalAuth: false
  }
}

resource teams 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: bot
  name: 'MsTeamsChannel'
  location: 'global'
  properties: {
    channelName: 'MsTeamsChannel'
    properties: { isEnabled: true, acceptedTerms: true }
  }
}

// Microsoft 365 channel (Microsoft 365 Copilot / Outlook) for custom engine agents
resource m365 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: bot
  name: 'M365Extensions'
  location: 'global'
  properties: {
    channelName: 'M365Extensions'
  }
}

resource oauth 'Microsoft.BotService/botServices/connections@2022-09-15' = if (!empty(graphAppClientId)) {
  parent: bot
  name: 'graph-sso'
  location: 'global'
  properties: {
    serviceProviderDisplayName: 'Azure Active Directory v2'
    serviceProviderId: '30dd229c-58e3-4a48-bdfd-91ec48eb906c'
    clientId: graphAppClientId
    clientSecret: graphAppClientSecret
    scopes: graphScopes
    parameters: [
      { key: 'tenantID', value: tenantId }
      { key: 'tokenExchangeUrl', value: 'api://botid-${msaAppId}' }
    ]
  }
}

output name string = bot.name
output id string = bot.id
