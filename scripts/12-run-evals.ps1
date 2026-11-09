<#
.SYNOPSIS  Runs the golden evaluation set (eval/golden_qa.jsonl) against the deployed API (/api/ask) and writes eval/results.
#>
param([string]$BaseUrl)
. "$PSScriptRoot/lib/common.ps1"
$out = Get-ProductIQOutputs
if (-not $BaseUrl) { $BaseUrl = "https://$($out['CONTAINER_APP_FQDN'])" }
Invoke-RepoPython 'eval/run_eval.py' @('--base-url', $BaseUrl)
