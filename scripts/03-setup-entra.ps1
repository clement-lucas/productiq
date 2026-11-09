<#
.SYNOPSIS  Creates the Entra app registration "ProductIQ-Graph" used by the bot OAuth connection (delegated Microsoft Graph
           permissions for the Collaboration Agent), stores its secret in Key Vault, configures Teams SSO, grants admin
           consent, then re-runs 02-deploy-infra.ps1 to create the "graph-sso" OAuth connection on the Azure Bot.
.NOTES     Requires Application Administrator (or Global Administrator for admin consent). Run 01-login.ps1 first.
#>
param([int]$SecretMonths = 6, [switch]$SkipRedeploy)
. "$PSScriptRoot/lib/common.ps1"
$cfg = Get-ProductIQConfig
$out = Get-ProductIQOutputs
if (-not $out.ContainsKey('BOT_APP_ID')) { throw 'Run 02-deploy-infra.ps1 first (BOT_APP_ID missing).' }
if (-not (Get-MgContext)) { throw 'Not connected to Microsoft Graph. Run 01-login.ps1.' }

$appName = "ProductIQ-Graph-$($cfg.environmentName)"
$botAppId = $out['BOT_APP_ID']
$graphResourceId = '00000003-0000-0000-c000-000000000000'
$delegated = @('User.Read', 'openid', 'profile', 'offline_access', 'Calendars.ReadWrite', 'OnlineMeetings.ReadWrite', 'Chat.Create',
               'Chat.ReadWrite', 'ChatMessage.Send', 'TeamsAppInstallation.ReadWriteForChat', 'People.Read')

Write-Step 'Resolving Microsoft Graph permission IDs'
$graphSp = Get-MgServicePrincipal -Filter "appId eq '$graphResourceId'"
$access = @()
foreach ($scope in $delegated) {
    $s = $graphSp.Oauth2PermissionScopes | Where-Object Value -eq $scope
    if (-not $s) { throw "Graph scope not found: $scope" }
    $access += @{ Id = $s.Id; Type = 'Scope' }
}

Write-Step "Creating or updating app registration $appName"
$app = Get-MgApplication -Filter "displayName eq '$appName'" | Select-Object -First 1
$scopeId = [guid]::NewGuid().ToString()
$apiBlock = @{
    RequestedAccessTokenVersion = 2
    Oauth2PermissionScopes = @(@{
        Id = $scopeId; Value = 'access_as_user'; Type = 'User'; IsEnabled = $true
        AdminConsentDisplayName = 'Access ProductIQ as the signed-in user'
        AdminConsentDescription = 'Allows Teams / Microsoft 365 Copilot to call ProductIQ on behalf of the signed-in user.'
        UserConsentDisplayName = 'Access ProductIQ as you'
        UserConsentDescription = 'Allows Teams to call ProductIQ on your behalf.'
    })
}
$body = @{
    DisplayName = $appName
    SignInAudience = 'AzureADMyOrg'
    Web = @{ RedirectUris = @('https://token.botframework.com/.auth/web/redirect') }
    RequiredResourceAccess = @(@{ ResourceAppId = $graphResourceId; ResourceAccess = $access })
    Notes = 'ProductIQ (Hack to Build 2026) – delegated Graph for meeting/chat creation after user approval.'
}
if (-not $app) {
    $app = New-MgApplication @body
    Update-MgApplication -ApplicationId $app.Id -Api $apiBlock
    Write-Ok "Created appId $($app.AppId)"
} else {
    Update-MgApplication -ApplicationId $app.Id @body
    Write-Ok "Updated appId $($app.AppId)"
}
$app = Get-MgApplication -ApplicationId $app.Id

# Teams SSO: identifier URI must be api://botid-<bot app id>; pre-authorise Teams / Microsoft 365 clients
Write-Step 'Configuring Teams SSO (identifier URI + pre-authorised Teams clients)'
$identifierUri = "api://botid-$botAppId"
$existingScope = $app.Api.Oauth2PermissionScopes | Where-Object Value -eq 'access_as_user' | Select-Object -First 1
if ($existingScope) { $scopeId = $existingScope.Id }
$teamsClients = @('1fec8e78-bce4-4aaf-ab1b-5451cc387264', '5e3ce6c0-2b1f-4285-8d4b-75ee78787346',  # Teams desktop/mobile, Teams web
                  '4765445b-32c6-49b0-83e6-1d93765276ca', '0ec893e0-5785-4de6-99da-4ed124e5296c',  # Microsoft 365 web, desktop
                  'd3590ed6-52b3-4102-aeff-aad2292ab01c', 'bc59ab01-8403-45c6-8796-ac3ef710b3e3',  # Office, Outlook web
                  '27922004-5251-4030-b22d-91ecd9a37ea4')                                          # Outlook mobile
Update-MgApplication -ApplicationId $app.Id -IdentifierUris @($identifierUri) -Api @{
    RequestedAccessTokenVersion = 2
    Oauth2PermissionScopes = @($app.Api.Oauth2PermissionScopes)
    PreAuthorizedApplications = @($teamsClients | ForEach-Object { @{ AppId = $_; DelegatedPermissionIds = @($scopeId) } })
}
Write-Ok "Identifier URI $identifierUri"

Write-Step 'Ensuring service principal and admin consent for delegated Graph permissions'
$sp = Get-MgServicePrincipal -Filter "appId eq '$($app.AppId)'" | Select-Object -First 1
if (-not $sp) { $sp = New-MgServicePrincipal -AppId $app.AppId }
$grant = Get-MgOauth2PermissionGrant -Filter "clientId eq '$($sp.Id)' and resourceId eq '$($graphSp.Id)'" | Select-Object -First 1
$scopeString = ($delegated -join ' ')
if ($grant) { Update-MgOauth2PermissionGrant -OAuth2PermissionGrantId $grant.Id -Scope $scopeString }
else { New-MgOauth2PermissionGrant -ClientId $sp.Id -ConsentType 'AllPrincipals' -ResourceId $graphSp.Id -Scope $scopeString | Out-Null }
Write-Ok 'Admin consent granted (AllPrincipals)'

Write-Step "Creating client secret ($SecretMonths months) and storing it in Key Vault"
$secret = Add-MgApplicationPassword -ApplicationId $app.Id -PasswordCredential @{
    DisplayName = "bot-oauth-$(Get-Date -Format yyyyMMdd)"; EndDateTime = (Get-Date).AddMonths($SecretMonths)
}
$kvName = ([uri]$out['KEY_VAULT_URI']).Host.Split('.')[0]
$tmp = New-TemporaryFile
try {
    Set-Content -Path $tmp -Value $secret.SecretText -NoNewline
    az keyvault secret set --vault-name $kvName --name graph-app-client-secret --file $tmp --only-show-errors | Out-Null
} finally { Remove-Item $tmp -Force }
Write-Ok "Secret stored in $kvName (never written to the repo)"

Set-ProductIQOutputs @{ GRAPH_APP_CLIENT_ID = $app.AppId; GRAPH_APP_OBJECT_ID = $app.Id; GRAPH_APP_IDENTIFIER_URI = $identifierUri }

if (-not $SkipRedeploy) {
    Write-Step 'Re-running infrastructure deployment to create the bot OAuth connection'
    & "$PSScriptRoot/02-deploy-infra.ps1"
}
Write-Host "`nEntra setup complete. Next: scripts/04-generate-data.ps1" -ForegroundColor Green
