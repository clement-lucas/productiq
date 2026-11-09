<#
.SYNOPSIS  Optional demo tenant setup: fictional product-team users, a Microsoft 365 group + Team "Contoso Product Development",
           and a SharePoint folder with the knowledge documents (the realistic source location for Foundry IQ).
.NOTES     Only for a lab/demo tenant (e.g. DIAx98389119.onmicrosoft.com). Demo passwords are stored in Key Vault, never printed.
#>
param([switch]$SkipUsers, [switch]$SkipTeam, [switch]$SkipDocs)
. "$PSScriptRoot/lib/common.ps1"
$cfg = Get-ProductIQConfig
$out = Get-ProductIQOutputs
if (-not (Get-MgContext)) { throw 'Not connected to Microsoft Graph. Run 01-login.ps1.' }
$domain = $cfg.tenantDomain
$kvName = ([uri]$out['KEY_VAULT_URI']).Host.Split('.')[0]

$people = @(
    @{ Alias = 'aiko.tanaka';  Name = 'Aiko Tanaka';  Title = 'Product Manager';      Dept = 'Product Development' }
    @{ Alias = 'ken.sato';     Name = 'Ken Sato';     Title = 'Design Lead';          Dept = 'Industrial Design' }
    @{ Alias = 'maria.garcia'; Name = 'Maria Garcia'; Title = 'Sourcing Lead';        Dept = 'Procurement' }
    @{ Alias = 'raj.patel';    Name = 'Raj Patel';    Title = 'Supply Chain Lead';    Dept = 'Supply Chain' }
)

function New-DemoPassword {
    $chars = @(48..57) + @(65..90) + @(97..122) + @(33, 35, 37, 42)
    (-join ($chars | Get-Random -Count 20 | ForEach-Object { [char]$_ })) + 'aA1!'
}

$memberIds = @()
if (-not $SkipUsers -and $cfg.demoUsers.create) {
    Write-Step 'Creating fictional demo users'
    $sku = Get-MgSubscribedSku | Where-Object { $_.PrepaidUnits.Enabled -gt $_.ConsumedUnits -and $_.SkuPartNumber -match 'SPE_E5|ENTERPRISEPREMIUM|SPE_E3|ENTERPRISEPACK|Microsoft_365_E' } | Select-Object -First 1
    $copilot = Get-MgSubscribedSku | Where-Object { $_.PrepaidUnits.Enabled -gt $_.ConsumedUnits -and $_.SkuPartNumber -match 'Copilot' } | Select-Object -First 1
    foreach ($p in $people) {
        $upn = "$($p.Alias)@$domain"
        $u = Get-MgUser -Filter "userPrincipalName eq '$upn'" -ErrorAction SilentlyContinue
        if (-not $u) {
            $pwd = if ($cfg.demoUsers.password) { $cfg.demoUsers.password } else { New-DemoPassword }
            $u = New-MgUser -DisplayName $p.Name -UserPrincipalName $upn -MailNickname ($p.Alias -replace '\.', '') -AccountEnabled `
                 -JobTitle $p.Title -Department $p.Dept -UsageLocation $cfg.demoUsers.usageLocation `
                 -PasswordProfile @{ Password = $pwd; ForceChangePasswordNextSignIn = $true }
            $tmp = New-TemporaryFile
            try { Set-Content $tmp $pwd -NoNewline; az keyvault secret set --vault-name $kvName --name "demo-user-$($p.Alias -replace '\.', '-')" --file $tmp --only-show-errors | Out-Null }
            finally { Remove-Item $tmp -Force }
            Write-Ok "$($p.Name) <$upn> (initial password in Key Vault secret demo-user-$($p.Alias -replace '\.', '-'))"
        } else { Write-Ok "$($p.Name) exists" }
        foreach ($s in @($sku, $copilot)) {
            if ($s) { try { Set-MgUserLicense -UserId $u.Id -AddLicenses @(@{ SkuId = $s.SkuId }) -RemoveLicenses @() | Out-Null } catch { Write-Warn2 "License $($s.SkuPartNumber) not assigned to $($p.Name): $($_.Exception.Message)" } }
        }
        $memberIds += $u.Id
    }
    if (-not $sku) { Write-Warn2 'No Microsoft 365 E3/E5 licence with free seats found – assign Teams licences manually.' }
}

if (-not $SkipTeam) {
    Write-Step 'Creating Microsoft 365 group + Team "Contoso Product Development"'
    $me = Invoke-MgGraphRequest -Method GET -Uri 'v1.0/me'
    $g = Get-MgGroup -Filter "displayName eq 'Contoso Product Development'" | Select-Object -First 1
    if (-not $g) {
        $g = New-MgGroup -DisplayName 'Contoso Product Development' -MailNickname 'contoso-productdev' -MailEnabled -SecurityEnabled:$false `
             -GroupTypes @('Unified') -Description 'ProductIQ demo – product development group (fictional, synthetic data)' `
             -Visibility Private -AdditionalProperties @{ 'owners@odata.bind' = @("https://graph.microsoft.com/v1.0/users/$($me.id)") }
        Start-Sleep -Seconds 20
    }
    foreach ($id in $memberIds) { try { New-MgGroupMember -GroupId $g.Id -DirectoryObjectId $id -ErrorAction Stop } catch { } }
    for ($i = 0; $i -lt 10; $i++) {
        try { Invoke-MgGraphRequest -Method PUT -Uri "v1.0/groups/$($g.Id)/team" -Body (@{ memberSettings = @{ allowCreateUpdateChannels = $true } } | ConvertTo-Json) -ContentType 'application/json' | Out-Null; break }
        catch { Start-Sleep -Seconds 15 }
    }
    Write-Ok "Group/Team id $($g.Id)"
    Set-ProductIQOutputs @{ M365_GROUP_ID = $g.Id }
    $out = Get-ProductIQOutputs
}

if (-not $SkipDocs -and $out.ContainsKey('M365_GROUP_ID')) {
    Write-Step 'Uploading knowledge documents to the group SharePoint library (folder "ProductIQ Knowledge")'
    $docs = Join-Path (Get-RepoRoot) 'data/output/knowledge'
    foreach ($f in Get-ChildItem $docs -Filter *.md) {
        $uri = "v1.0/groups/$($out['M365_GROUP_ID'])/drive/root:/ProductIQ%20Knowledge/$($f.Name):/content"
        for ($i = 0; $i -lt 6; $i++) {
            try { Invoke-MgGraphRequest -Method PUT -Uri $uri -InputFilePath $f.FullName -ContentType 'text/markdown' | Out-Null; break }
            catch { Start-Sleep -Seconds 20 }   # the group site can take a few minutes to provision
        }
        Write-Ok $f.Name
    }
    Write-Host '    Tip: add a "remote SharePoint" knowledge source to the knowledge base for permission-aware retrieval (preview).'
}
Write-Host "`nM365 demo setup complete. Next: scripts/09-build-teams-app.ps1" -ForegroundColor Green
