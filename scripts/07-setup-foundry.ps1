<#
.SYNOPSIS  Creates Foundry project connections (Fabric IQ, Foundry IQ knowledge base), the specialist prompt agents, and runs a smoke test.
.PARAMETER FabricAuth  user (default, identity passthrough) or project (Foundry project managed identity).
#>
param([ValidateSet('user', 'project')][string]$FabricAuth = 'user', [switch]$SkipSmokeTest)
. "$PSScriptRoot/lib/common.ps1"
Set-AzContextFromConfig (Get-ProductIQConfig)
Write-Step 'Project connections'
Invoke-RepoPython 'scripts/foundry/create_connections.py' @('--fabric-auth', $FabricAuth)
Write-Step 'Specialist agents'
Invoke-RepoPython 'scripts/foundry/create_agents.py'
if (-not $SkipSmokeTest) {
    Write-Step 'Smoke test'
    Invoke-RepoPython 'scripts/foundry/smoke_test.py'
}
Write-Host "`nFoundry ready. Next: scripts/08-setup-m365.ps1" -ForegroundColor Green
