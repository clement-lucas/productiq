<#
.SYNOPSIS  Suspend / resume / show the Fabric capacity to control cost (an idle F SKU still bills while Active).
.EXAMPLE   ./scripts/fabric-capacity.ps1 -Action Suspend
#>
param([Parameter(Mandatory)][ValidateSet('Suspend', 'Resume', 'Status')][string]$Action)
. "$PSScriptRoot/lib/common.ps1"
Set-AzContextFromConfig (Get-ProductIQConfig)
$id = (Get-ProductIQOutputs)['FABRIC_CAPACITY_ID']
if (-not $id) { throw 'FABRIC_CAPACITY_ID missing (deployFabricCapacity=false?)' }
switch ($Action) {
    'Suspend' { az rest --method post --url "https://management.azure.com$id/suspend?api-version=2023-11-01" | Out-Null; Write-Ok 'Suspend requested' }
    'Resume'  { az rest --method post --url "https://management.azure.com$id/resume?api-version=2023-11-01" | Out-Null; Write-Ok 'Resume requested' }
}
$state = az rest --method get --url "https://management.azure.com$($id)?api-version=2023-11-01" --query properties.state -o tsv
Write-Ok "Capacity state: $state"
