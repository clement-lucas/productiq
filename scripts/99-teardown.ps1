<#
.SYNOPSIS  Deletes the ProductIQ Azure resource group (and optionally the Entra app, demo users, Teams app). Irreversible.
#>
param([switch]$IncludeEntra, [switch]$IncludeDemoUsers, [switch]$Force)
. "$PSScriptRoot/lib/common.ps1"
$cfg = Get-ProductIQConfig
Set-AzContextFromConfig $cfg
$out = Get-ProductIQOutputs
$rg = $out['AZURE_RESOURCE_GROUP']
if (-not $Force) {
    $answer = Read-Host "Type the resource group name '$rg' to delete it"
    if ($answer -ne $rg) { Write-Warn2 'Cancelled'; return }
}
Write-Step "Deleting resource group $rg"
az group delete -n $rg --yes --no-wait
Write-Ok 'Deletion started (Key Vault and Foundry resources stay soft-deleted for their retention period; purge in the portal if needed).'
if ($IncludeEntra -and $out['GRAPH_APP_OBJECT_ID']) { Remove-MgApplication -ApplicationId $out['GRAPH_APP_OBJECT_ID']; Write-Ok 'Entra app removed' }
if ($IncludeEntra -and $out['TEAMS_APP_CATALOG_ID']) { Invoke-MgGraphRequest -Method DELETE -Uri "v1.0/appCatalogs/teamsApps/$($out['TEAMS_APP_CATALOG_ID'])"; Write-Ok 'Teams app removed' }
if ($IncludeDemoUsers) {
    foreach ($a in @('aiko.tanaka', 'ken.sato', 'maria.garcia', 'raj.patel')) {
        $u = Get-MgUser -Filter "userPrincipalName eq '$a@$($cfg.tenantDomain)'" -ErrorAction SilentlyContinue
        if ($u) { Remove-MgUser -UserId $u.Id; Write-Ok "Removed $a" }
    }
}
Write-Host 'Fabric workspace is not deleted automatically – remove "ProductIQ-<env>" in the Fabric portal if no longer needed.'
