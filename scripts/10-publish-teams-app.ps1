<#
.SYNOPSIS  Publishes (or updates) the ProductIQ app in the organisation's Teams app catalog and records TEAMS_APP_CATALOG_ID.
.NOTES     Needs Teams Administrator (AppCatalog.ReadWrite.All). In Teams admin center, allow the app and, for Microsoft 365
           Copilot, make sure custom engine agents are allowed for the demo users.
#>
. "$PSScriptRoot/lib/common.ps1"
$out = Get-ProductIQOutputs
if (-not (Get-MgContext)) { throw 'Not connected to Microsoft Graph. Run 01-login.ps1.' }
$zip = $out['TEAMS_APP_PACKAGE']
if (-not $zip -or -not (Test-Path $zip)) { throw 'Run 09-build-teams-app.ps1 first.' }

$existing = Invoke-MgGraphRequest -Method GET -Uri "v1.0/appCatalogs/teamsApps?`$filter=externalId eq '$($out['TEAMS_APP_ID'])'"
if ($existing.value.Count -gt 0) {
    $catalogId = $existing.value[0].id
    Write-Step "Updating app $catalogId"
    Invoke-MgGraphRequest -Method POST -Uri "v1.0/appCatalogs/teamsApps/$catalogId/appDefinitions" -InputFilePath $zip -ContentType 'application/zip' | Out-Null
} else {
    Write-Step 'Publishing app to the org catalog'
    $res = Invoke-MgGraphRequest -Method POST -Uri 'v1.0/appCatalogs/teamsApps' -InputFilePath $zip -ContentType 'application/zip'
    $catalogId = $res.id
}
Set-ProductIQOutputs @{ TEAMS_APP_CATALOG_ID = $catalogId }
Write-Ok "TEAMS_APP_CATALOG_ID = $catalogId"

$cfg = Get-ProductIQConfig
Set-AzContextFromConfig $cfg
az containerapp update -n $out['CONTAINER_APP_NAME'] -g $out['AZURE_RESOURCE_GROUP'] --set-env-vars "TEAMS_APP_CATALOG_ID=$catalogId" --only-show-errors | Out-Null
Write-Ok 'Container app updated with TEAMS_APP_CATALOG_ID'
Write-Host "`nIn Teams: Apps > Built for your org > ProductIQ > Add. In Microsoft 365 Copilot: open the agent from the right pane." -ForegroundColor Green
