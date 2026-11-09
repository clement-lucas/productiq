<#
.SYNOPSIS  Uploads knowledge documents to Blob Storage and creates the Foundry IQ knowledge source + knowledge base in Azure AI Search.
#>
param([switch]$SkipUpload)
. "$PSScriptRoot/lib/common.ps1"
Set-AzContextFromConfig (Get-ProductIQConfig)
$a = @(); if ($SkipUpload) { $a += '--skip-upload' }
Invoke-RepoPython 'scripts/foundry/setup_knowledge.py' $a
