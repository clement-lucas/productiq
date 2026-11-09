<#
.SYNOPSIS  Builds the ProductIQ API image in Azure Container Registry (no local Docker needed) and rolls it out to Container Apps.
#>
param([string]$Tag = (Get-Date -Format 'yyyyMMddHHmm'))
. "$PSScriptRoot/lib/common.ps1"
$cfg = Get-ProductIQConfig
Set-AzContextFromConfig $cfg
$out = Get-ProductIQOutputs
$root = Get-RepoRoot
$image = "$($out['ACR_LOGIN_SERVER'])/productiq-api:$Tag"

Write-Step "Building $image in ACR"
az acr build --registry $out['ACR_NAME'] --image "productiq-api:$Tag" --file (Join-Path $root 'src/Dockerfile') (Join-Path $root 'src') --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'ACR build failed' }

$envKeys = @('FABRIC_WORKSPACE_ID', 'FABRIC_DATA_AGENT_ID', 'FABRIC_DATA_AGENT_MCP_URL', 'FABRIC_IQ_CONNECTION_NAME', 'KB_MCP_CONNECTION_NAME',
             'BING_CONNECTION_NAME', 'TEAMS_APP_CATALOG_ID', 'GRAPH_APP_CLIENT_ID', 'SEARCH_KNOWLEDGE_BASE', 'COSMOS_DATABASE')
$pairs = @(); foreach ($k in $envKeys) { if ($out.ContainsKey($k) -and $out[$k]) { $pairs += "$k=$($out[$k])" } }

Write-Step 'Rolling out to Container Apps'
az containerapp update -n $out['CONTAINER_APP_NAME'] -g $out['AZURE_RESOURCE_GROUP'] --image $image --set-env-vars @pairs --only-show-errors | Out-Null
az containerapp ingress update -n $out['CONTAINER_APP_NAME'] -g $out['AZURE_RESOURCE_GROUP'] --target-port 8000 --only-show-errors | Out-Null
Start-Sleep -Seconds 20
try { $h = Invoke-RestMethod "https://$($out['CONTAINER_APP_FQDN'])/healthz" -TimeoutSec 30; Write-Ok "Health: $($h | ConvertTo-Json -Compress)" }
catch { Write-Warn2 "Health check failed – inspect logs: az containerapp logs show -n $($out['CONTAINER_APP_NAME']) -g $($out['AZURE_RESOURCE_GROUP']) --follow" }
Write-Host "`nApp deployed: https://$($out['CONTAINER_APP_FQDN'])" -ForegroundColor Green
