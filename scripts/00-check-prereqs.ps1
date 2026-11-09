<#
.SYNOPSIS  Checks local tools and creates the Python virtual environment (.venv) with all script dependencies.
.NOTES     Requires PowerShell 7+, Azure CLI 2.65+, Python 3.11+, Git. Optional: Docker (not required – images build in ACR).
#>
. "$PSScriptRoot/lib/common.ps1"

Write-Step 'Checking tools'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7+ is required (https://aka.ms/powershell).' }
Write-Ok "PowerShell $($PSVersionTable.PSVersion)"
Assert-Command 'az' 'Install the Azure CLI: https://aka.ms/installazurecli'
Write-Ok "Azure CLI $((az version | ConvertFrom-Json).'azure-cli')"
az bicep version 2>$null | Out-Null; if ($LASTEXITCODE -ne 0) { az bicep install | Out-Null }
Write-Ok 'Bicep CLI'
Assert-Command 'git' 'Install Git: https://git-scm.com'
$py = Get-Python
$ver = & $py -c "import sys;print('%d.%d'%sys.version_info[:2])"
if ([version]$ver -lt [version]'3.11') { throw "Python 3.11+ required (found $ver)." }
Write-Ok "Python $ver"

Write-Step 'Checking PowerShell modules (Microsoft Graph)'
foreach ($m in @('Microsoft.Graph.Authentication', 'Microsoft.Graph.Applications', 'Microsoft.Graph.Users', 'Microsoft.Graph.Groups', 'Microsoft.Graph.Teams')) {
    if (-not (Get-Module -ListAvailable -Name $m)) {
        Write-Warn2 "Installing $m (CurrentUser)"
        Install-Module $m -Scope CurrentUser -Force -AllowClobber
    }
    Write-Ok $m
}

Write-Step 'Creating Python virtual environment (.venv)'
$root = Get-RepoRoot
if (-not (Test-Path (Join-Path $root '.venv'))) { & $py -m venv (Join-Path $root '.venv') }
$venvPy = if ($IsWindows) { Join-Path $root '.venv/Scripts/python.exe' } else { Join-Path $root '.venv/bin/python' }
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r (Join-Path $root 'scripts/requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
Write-Ok 'Python dependencies installed'
Write-Host "`nAll prerequisites OK. Next: scripts/01-login.ps1" -ForegroundColor Green
