<#
.SYNOPSIS  Signs in to Azure CLI and Microsoft Graph PowerShell for the tenant/subscription in config/environment.json.
#>
. "$PSScriptRoot/lib/common.ps1"
$cfg = Get-ProductIQConfig

Write-Step "Azure CLI sign-in (tenant $($cfg.tenantDomain))"
az login --tenant $cfg.tenantId --only-show-errors | Out-Null
az account set --subscription $cfg.subscriptionId
$acct = az account show | ConvertFrom-Json
Write-Ok "Subscription: $($acct.name) ($($acct.id))"

Write-Step 'Registering resource providers (idempotent)'
foreach ($ns in @('Microsoft.CognitiveServices', 'Microsoft.Search', 'Microsoft.DocumentDB', 'Microsoft.App', 'Microsoft.ContainerRegistry',
                  'Microsoft.OperationalInsights', 'Microsoft.Insights', 'Microsoft.KeyVault', 'Microsoft.Storage', 'Microsoft.BotService',
                  'Microsoft.Fabric', 'Microsoft.Bing', 'Microsoft.ManagedIdentity')) {
    az provider register --namespace $ns --only-show-errors | Out-Null
    Write-Ok $ns
}

Write-Step 'Microsoft Graph PowerShell sign-in (needs admin for app registration, consent, users and Teams app catalog)'
$scopes = @('Application.ReadWrite.All', 'DelegatedPermissionGrant.ReadWrite.All', 'AppRoleAssignment.ReadWrite.All',
            'User.ReadWrite.All', 'Group.ReadWrite.All', 'Directory.ReadWrite.All', 'AppCatalog.ReadWrite.All',
            'TeamMember.ReadWrite.All', 'Sites.ReadWrite.All', 'Organization.Read.All')
Connect-MgGraph -TenantId $cfg.tenantId -Scopes $scopes -NoWelcome
$ctx = Get-MgContext
Write-Ok "Graph: $($ctx.Account)"
Write-Host "`nSigned in. Next: scripts/02-deploy-infra.ps1" -ForegroundColor Green
