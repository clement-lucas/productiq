<#
.SYNOPSIS  Generates the synthetic Contoso Home Appliances dataset (24 months) and knowledge documents into data/output.
#>
param([int]$Seed = 42, [double]$Scale = 1.0)
. "$PSScriptRoot/lib/common.ps1"
Write-Step "Generating synthetic data (seed $Seed, scale $Scale)"
Invoke-RepoPython 'data/generator/generate_data.py' @('--out', (Join-Path (Get-RepoRoot) 'data/output'), '--seed', "$Seed", '--scale', "$Scale")
Write-Step 'Building the evaluation set from the generated data'
Invoke-RepoPython 'eval/build_golden.py'
Write-Host "`nData ready in data/output. Next: scripts/05-setup-fabric.ps1" -ForegroundColor Green
