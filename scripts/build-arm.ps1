<#
.SYNOPSIS  Compiles infra/main.bicep to infra/arm/azuredeploy.json (ARM) and writes a parameters template.
#>
. "$PSScriptRoot/lib/common.ps1"
$root = Get-RepoRoot
az bicep build --file (Join-Path $root 'infra/main.bicep') --outfile (Join-Path $root 'infra/arm/azuredeploy.json')
if ($LASTEXITCODE -ne 0) { throw 'Bicep build failed' }
$cfg = Get-ProductIQConfig
$me = az ad signed-in-user show --query id -o tsv 2>$null
@{
    '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    contentVersion = '1.0.0.0'
    parameters = @{
        environmentName = @{ value = $cfg.environmentName }; prefix = @{ value = $cfg.prefix }; location = @{ value = $cfg.location }
        deployerPrincipalId = @{ value = ($me ? $me : '<object-id-of-the-deploying-user>') }
        fabricAdminMembers = @{ value = @($(if ($cfg.fabricAdminUpn) { $cfg.fabricAdminUpn } else { '<admin-upn>' })) }
    }
} | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $root 'infra/arm/azuredeploy.parameters.json') -Encoding utf8
Write-Ok 'infra/arm/azuredeploy.json and azuredeploy.parameters.json written'
