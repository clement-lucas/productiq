<#
.SYNOPSIS  Deploys infra/main.bicep at subscription scope and writes outputs to config/outputs.json and .env.
.DESCRIPTION
  Run once before 03-setup-entra.ps1 (bot OAuth connection is skipped), and again afterwards
  (03 re-runs it automatically) so the "graph-sso" OAuth connection is created with the secret from Key Vault.
.PARAMETER WhatIf  Show the what-if preview only.
#>
param([switch]$WhatIf)
. "$PSScriptRoot/lib/common.ps1"
$cfg = Get-ProductIQConfig
Set-AzContextFromConfig $cfg
$root = Get-RepoRoot
$out = Get-ProductIQOutputs

Write-Step 'Resolving deployer identity'
$me = az ad signed-in-user show | ConvertFrom-Json
$fabricAdmin = if ([string]::IsNullOrWhiteSpace($cfg.fabricAdminUpn)) { $me.userPrincipalName } else { $cfg.fabricAdminUpn }
Write-Ok "Deployer: $($me.userPrincipalName) ($($me.id)); Fabric admin: $fabricAdmin"

# Graph app (created by 03-setup-entra.ps1) – secret is read from Key Vault, never from disk
$graphClientId = if ($out.ContainsKey('GRAPH_APP_CLIENT_ID')) { $out['GRAPH_APP_CLIENT_ID'] } else { '' }
$graphSecret = ''
if ($graphClientId -and $out.ContainsKey('KEY_VAULT_URI')) {
    $kvName = ([uri]$out['KEY_VAULT_URI']).Host.Split('.')[0]
    $graphSecret = az keyvault secret show --vault-name $kvName --name graph-app-client-secret --query value -o tsv 2>$null
    if ($graphSecret) { Write-Ok 'Graph app secret found in Key Vault – bot OAuth connection will be configured' }
}

$params = @{
    '$schema'        = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    contentVersion   = '1.0.0.0'
    parameters       = @{
        environmentName        = @{ value = $cfg.environmentName }
        prefix                 = @{ value = $cfg.prefix }
        location               = @{ value = $cfg.location }
        tenantId               = @{ value = $cfg.tenantId }
        deployerPrincipalId    = @{ value = $me.id }
        deployerPrincipalType  = @{ value = 'User' }
        deployFabricCapacity   = @{ value = [bool]$cfg.deployFabricCapacity }
        fabricSku              = @{ value = $cfg.fabricSku }
        fabricAdminMembers     = @{ value = @($fabricAdmin) }
        reasoningModelName     = @{ value = $cfg.models.reasoning.name }
        reasoningModelVersion  = @{ value = $cfg.models.reasoning.version }
        reasoningModelCapacity = @{ value = [int]$cfg.models.reasoning.capacity }
        routerModelName        = @{ value = $cfg.models.router.name }
        routerModelVersion     = @{ value = $cfg.models.router.version }
        routerModelCapacity    = @{ value = [int]$cfg.models.router.capacity }
        embeddingModelName     = @{ value = $cfg.models.embedding.name }
        embeddingModelVersion  = @{ value = $cfg.models.embedding.version }
        embeddingModelCapacity = @{ value = [int]$cfg.models.embedding.capacity }
        enableBingGrounding    = @{ value = [bool]$cfg.enableBingGrounding }
        graphAppClientId       = @{ value = $graphClientId }
        graphAppClientSecret   = @{ value = [string]$graphSecret }
    }
}
$tmp = New-TemporaryFile
try {
    ($params | ConvertTo-Json -Depth 10) | Set-Content $tmp -Encoding utf8
    $name = "productiq-$($cfg.environmentName)-$(Get-Date -Format 'yyyyMMddHHmm')"
    $template = Join-Path $root 'infra/main.bicep'
    if ($WhatIf) {
        Write-Step 'What-if preview'
        az deployment sub what-if --name $name --location $cfg.location --template-file $template --parameters "@$tmp"
        return
    }
    Write-Step "Deploying $template to $($cfg.location) (10–25 min on first run)"
    $result = az deployment sub create --name $name --location $cfg.location --template-file $template --parameters "@$tmp" --only-show-errors | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $result) { throw 'Deployment failed – see the Azure portal > Subscription > Deployments for details.' }
}
finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }

$values = @{}
foreach ($p in $result.properties.outputs.PSObject.Properties) { $values[$p.Name] = $p.Value.value }
$values['COSMOS_DATABASE'] = 'productiq'
$values['SEARCH_KNOWLEDGE_BASE'] = 'productiq-kb'
$values['FABRIC_IQ_CONNECTION_NAME'] = 'fabriciq-dataagent'
$values['KB_MCP_CONNECTION_NAME'] = 'foundryiq-kb'
Set-ProductIQOutputs $values
Write-Ok "Outputs saved to config/outputs.json and .env"
Write-Host "`nInfrastructure ready. Foundry project endpoint: $($values['FOUNDRY_PROJECT_ENDPOINT'])" -ForegroundColor Green
if (-not $graphClientId) { Write-Host 'Next: scripts/03-setup-entra.ps1' -ForegroundColor Green }
