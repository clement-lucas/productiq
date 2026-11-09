<#
.SYNOPSIS  Runs the full ProductIQ setup end-to-end (each step is idempotent and can be re-run on its own).
.EXAMPLE   ./scripts/deploy-all.ps1            # everything
           ./scripts/deploy-all.ps1 -From 5    # resume from step 05
#>
param([int]$From = 0, [int]$To = 11)
$steps = [ordered]@{
    0 = '00-check-prereqs.ps1'; 1 = '01-login.ps1'; 2 = '02-deploy-infra.ps1'; 3 = '03-setup-entra.ps1'; 4 = '04-generate-data.ps1'
    5 = '05-setup-fabric.ps1'; 6 = '06-setup-knowledge.ps1'; 7 = '07-setup-foundry.ps1'; 8 = '08-setup-m365.ps1'
    9 = '09-build-teams-app.ps1'; 10 = '10-publish-teams-app.ps1'; 11 = '11-deploy-app.ps1'
}
foreach ($k in $steps.Keys) {
    if ($k -lt $From -or $k -gt $To) { continue }
    Write-Host "`n################ Step $($steps[$k]) ################" -ForegroundColor Magenta
    & (Join-Path $PSScriptRoot $steps[$k])
    if (-not $?) { throw "Step $($steps[$k]) failed. Fix the issue and resume with -From $k" }
}
Write-Host "`nProductIQ environment is ready. Run scripts/12-run-evals.ps1 to score the agent." -ForegroundColor Green
