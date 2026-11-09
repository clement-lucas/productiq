<#
.SYNOPSIS  Creates the Fabric workspace, lakehouse, notebooks and data agent; uploads bronze data and runs the medallion pipeline.
.NOTES     Fabric admin portal settings must be enabled first (see README "Fabric tenant settings").
#>
param([switch]$SkipUpload, [switch]$SkipRun, [switch]$SkipAgent)
. "$PSScriptRoot/lib/common.ps1"
$cfg = Get-ProductIQConfig
Set-AzContextFromConfig $cfg
$args2 = @('--env', $cfg.environmentName)
if ($SkipUpload) { $args2 += '--skip-upload' }
if ($SkipRun)    { $args2 += '--skip-run' }
if ($SkipAgent)  { $args2 += '--skip-agent' }
Invoke-RepoPython 'scripts/fabric/setup_fabric.py' $args2
