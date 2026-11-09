// Example parameter file. scripts/03-deploy-infra.ps1 passes values from config/environment.json instead.
using 'main.bicep'

param environmentName = 'dev'
param prefix = 'piq'
param location = 'eastus2'
param deployerPrincipalId = '<object-id-of-the-deploying-user>'
param deployFabricCapacity = true
param fabricSku = 'F2'
param fabricAdminMembers = [ '<admin-upn>' ]
param reasoningModelName = 'gpt-5.4'
param routerModelName = 'gpt-5.4-mini'
param embeddingModelName = 'text-embedding-3-large'
param enableBingGrounding = true
