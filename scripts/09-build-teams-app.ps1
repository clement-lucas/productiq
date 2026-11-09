<#
.SYNOPSIS  Builds the Teams / Microsoft 365 Copilot app package (custom engine agent) from teams-app/manifest.template.json.
#>
param([string]$Version = '1.0.0')
. "$PSScriptRoot/lib/common.ps1"
$out = Get-ProductIQOutputs
foreach ($k in @('BOT_APP_ID', 'CONTAINER_APP_FQDN', 'GRAPH_APP_CLIENT_ID')) { if (-not $out.ContainsKey($k) -or -not $out[$k]) { throw "$k missing – run 02 and 03 first." } }
if (-not $out.ContainsKey('TEAMS_APP_ID')) { Set-ProductIQOutputs @{ TEAMS_APP_ID = [guid]::NewGuid().ToString() }; $out = Get-ProductIQOutputs }

$root = Get-RepoRoot
$src = Join-Path $root 'teams-app'
$build = Join-Path $src 'build'
New-Item -ItemType Directory -Force -Path $build | Out-Null
$staging = Join-Path $build 'staging'
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $staging | Out-Null

$manifest = Get-Content (Join-Path $src 'manifest.template.json') -Raw
$map = @{ APP_VERSION = $Version; TEAMS_APP_ID = $out['TEAMS_APP_ID']; BOT_APP_ID = $out['BOT_APP_ID'];
          APP_FQDN = $out['CONTAINER_APP_FQDN']; GRAPH_APP_CLIENT_ID = $out['GRAPH_APP_CLIENT_ID'] }
foreach ($k in $map.Keys) { $manifest = $manifest.Replace("{{$k}}", $map[$k]) }
if ($manifest -match '\{\{[A-Z_]+\}\}') { throw "Unresolved placeholder in manifest: $($Matches[0])" }
$manifest | Set-Content (Join-Path $staging 'manifest.json') -Encoding utf8
Copy-Item (Join-Path $src 'color.png'), (Join-Path $src 'outline.png') $staging
$zip = Join-Path $build "productiq-teams-app-$Version.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zip
Set-ProductIQOutputs @{ TEAMS_APP_PACKAGE = $zip; TEAMS_APP_VERSION = $Version }
Write-Ok "Package: $zip"
Write-Host 'Validate it in the Teams Developer Portal (Apps > Import app) if you want a schema check. Next: scripts/10-publish-teams-app.ps1' -ForegroundColor Green
