[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,
    [string]$ResourceGroup = "rg-fornello-orders-swc",
    [ValidatePattern('^[a-z][a-z0-9-]{2,29}$')]
    [string]$Prefix = "fornello-orders",
    [ValidateSet("swedencentral")]
    [string]$Location = "swedencentral"
)

$ErrorActionPreference = "Stop"

function Invoke-Azure {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $result = & az @Arguments --subscription $SubscriptionId --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command '$($Arguments[0]) $($Arguments[1])' failed (exit $LASTEXITCODE)."
    }
    return $result
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Install Azure CLI first: https://learn.microsoft.com/cli/azure/install-azure-cli"
}
Invoke-Azure account show --output none
foreach ($provider in @("Microsoft.Storage", "Microsoft.Web", "Microsoft.Network", "Microsoft.App")) {
    $registration = Invoke-Azure provider show --namespace $provider --query registrationState --output tsv
    if ($registration -ne "Registered") {
        Write-Host "Registering Azure resource provider $provider..."
        Invoke-Azure provider register --namespace $provider --wait --output none
    }
}

$sha = [System.Security.Cryptography.SHA256]::Create()
try {
    $hash = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes("$SubscriptionId/$ResourceGroup/$Prefix"))
    $suffix = ([System.BitConverter]::ToString($hash)).Replace("-", "").Substring(0, 8).ToLowerInvariant()
} finally {
    $sha.Dispose()
}
$appName = "$Prefix-$suffix"
$storagePrefix = $Prefix.Replace("-", "")
if ($storagePrefix.Length -gt 12) { $storagePrefix = $storagePrefix.Substring(0, 12) }
$storageName = "st$storagePrefix$suffix"
$local = Join-Path $PSScriptRoot ".local"
New-Item -ItemType Directory -Path $local -Force | Out-Null

Write-Host "Deploying demo order API in $Location (resource group: $ResourceGroup)."
Invoke-Azure group create --name $ResourceGroup --location $Location --output none
$resources = @(Invoke-Azure resource list --resource-group $ResourceGroup --output json | ConvertFrom-Json)
if (-not ($resources | Where-Object { $_.type -eq "Microsoft.Storage/storageAccounts" -and $_.name -eq $storageName })) {
    Invoke-Azure storage account create --resource-group $ResourceGroup --name $storageName `
        --location $Location --sku Standard_LRS --kind StorageV2 --https-only true `
        --min-tls-version TLS1_2 --allow-blob-public-access false `
        --allow-shared-key-access false --public-network-access Disabled --output none
}
$storage = Invoke-Azure storage account show --resource-group $ResourceGroup --name $storageName --output json |
    ConvertFrom-Json
if ($storage.publicNetworkAccess -ne "Disabled" -or $storage.allowSharedKeyAccess -ne $false `
    -or $storage.allowBlobPublicAccess -ne $false) {
    throw "Storage must have public network access, Shared Key and anonymous blob access disabled."
}
$vnetName = "vnet-$appName"
if (-not ($resources | Where-Object { $_.type -eq "Microsoft.Network/virtualNetworks" -and $_.name -eq $vnetName })) {
    Invoke-Azure network vnet create --resource-group $ResourceGroup --name $vnetName `
        --location $Location --address-prefixes 10.42.0.0/24 `
        --subnet-name functions --subnet-prefixes 10.42.0.0/26 --output none
}
$subnets = @(Invoke-Azure network vnet subnet list --resource-group $ResourceGroup `
    --vnet-name $vnetName --output json | ConvertFrom-Json)
$integrationSubnet = $subnets | Where-Object name -eq functions
if (-not $integrationSubnet) {
    Invoke-Azure network vnet subnet create --resource-group $ResourceGroup --vnet-name $vnetName `
        --name functions --address-prefixes 10.42.0.0/26 --delegations Microsoft.App/environments --output none
} elseif (-not ($integrationSubnet.delegations | Where-Object serviceName -eq "Microsoft.App/environments")) {
    Invoke-Azure network vnet subnet update --resource-group $ResourceGroup --vnet-name $vnetName `
        --name functions --delegations Microsoft.App/environments --output none
}
if (-not ($subnets | Where-Object name -eq endpoints)) {
    Invoke-Azure network vnet subnet create --resource-group $ResourceGroup --vnet-name $vnetName `
        --name endpoints --address-prefixes 10.42.0.64/26 --private-endpoint-network-policies Disabled --output none
}
$vnet = Invoke-Azure network vnet show --resource-group $ResourceGroup --name $vnetName --output json |
    ConvertFrom-Json
foreach ($service in @("blob", "queue", "table")) {
    $zone = "privatelink.$service.core.windows.net"
    if (-not ($resources | Where-Object { $_.type -eq "Microsoft.Network/privateDnsZones" -and $_.name -eq $zone })) {
        Invoke-Azure network private-dns zone create --resource-group $ResourceGroup --name $zone --output none
    }
    if (-not ($resources | Where-Object {
        $_.type -eq "Microsoft.Network/privateDnsZones/virtualNetworkLinks" -and $_.name -eq "$zone/$appName-link"
    })) {
        Invoke-Azure network private-dns link vnet create --resource-group $ResourceGroup --zone-name $zone `
            --name "$appName-link" --virtual-network $vnet.id --registration-enabled false --output none
    }
    $endpoint = "pe-$appName-$service"
    if (-not ($resources | Where-Object { $_.type -eq "Microsoft.Network/privateEndpoints" -and $_.name -eq $endpoint })) {
        Invoke-Azure network private-endpoint create --resource-group $ResourceGroup --name $endpoint `
            --location $Location --vnet-name $vnetName --subnet endpoints `
            --private-connection-resource-id $storage.id --group-id $service `
            --connection-name "$endpoint-connection" --output none
    }
    $dns = Invoke-Azure network private-dns zone show --resource-group $ResourceGroup --name $zone --output json |
        ConvertFrom-Json
    $groups = @(Invoke-Azure network private-endpoint dns-zone-group list --resource-group $ResourceGroup `
        --endpoint-name $endpoint --output json | ConvertFrom-Json)
    if (-not ($groups | Where-Object name -eq default)) {
        Invoke-Azure network private-endpoint dns-zone-group create --resource-group $ResourceGroup `
            --endpoint-name $endpoint --name default --private-dns-zone $dns.id --zone-name $service --output none
    }
}
$containers = @(Invoke-Azure storage container-rm list --resource-group $ResourceGroup `
    --storage-account $storageName --output json | ConvertFrom-Json)
if (-not ($containers | Where-Object name -eq deployments)) {
    Invoke-Azure storage container-rm create --resource-group $ResourceGroup --storage-account $storageName `
        --name deployments --public-access off --output none
}
if (-not ($resources | Where-Object { $_.type -eq "Microsoft.Web/sites" -and $_.name -eq $appName })) {
    Invoke-Azure functionapp create --resource-group $ResourceGroup --name $appName `
        --storage-account $storageName --flexconsumption-location $Location `
        --runtime python --runtime-version 3.14 --instance-memory 2048 `
        --maximum-instance-count 40 --https-only true --disable-app-insights true `
        --assign-identity '[system]' --deployment-storage-auth-type SystemAssignedIdentity `
        --deployment-storage-container-name deployments --vnet $vnetName --subnet functions --output none
}
$app = Invoke-Azure functionapp show --resource-group $ResourceGroup --name $appName --output json | ConvertFrom-Json
if (-not $app.identity.principalId) { throw "The Function App requires its system-assigned identity." }
$assignments = @(Invoke-Azure role assignment list --scope $storage.id --output json | ConvertFrom-Json)
foreach ($role in @("Storage Blob Data Owner", "Storage Queue Data Contributor", "Storage Table Data Contributor")) {
    if (-not ($assignments | Where-Object { $_.principalId -eq $app.identity.principalId -and $_.roleDefinitionName -eq $role })) {
        Invoke-Azure role assignment create --assignee-object-id $app.identity.principalId `
            --assignee-principal-type ServicePrincipal --role $role --scope $storage.id --output none
    }
}
Invoke-Azure functionapp config appsettings delete --resource-group $ResourceGroup --name $appName `
    --setting-names AzureWebJobsStorage --output none
Invoke-Azure functionapp config appsettings set --resource-group $ResourceGroup --name $appName `
    --settings "AzureWebJobsStorage__accountName=$storageName" "AzureWebJobsStorage__credential=managedidentity" --output none

$zip = Join-Path ([System.IO.Path]::GetTempPath()) ("fornello-orders-" + [guid]::NewGuid().ToString("N") + ".zip")
try {
    $files = @("function_app.py", "orders.py", "host.json", "requirements.txt", "openapi.json") |
        ForEach-Object { Join-Path $PSScriptRoot $_ }
    Compress-Archive -LiteralPath $files -DestinationPath $zip
    Invoke-Azure functionapp deployment source config-zip --resource-group $ResourceGroup `
        --name $appName --src $zip --build-remote true --timeout 600 --output none
} finally {
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip }
}

$keys = Invoke-Azure functionapp function keys list --resource-group $ResourceGroup --name $appName `
    --function-name submit_order --output json | ConvertFrom-Json
if (-not $keys.hackathon) {
    Invoke-Azure functionapp function keys set --resource-group $ResourceGroup --name $appName `
        --function-name submit_order --key-name hackathon --output none
    $keys = Invoke-Azure functionapp function keys list --resource-group $ResourceGroup --name $appName `
        --function-name submit_order --output json | ConvertFrom-Json
}
if (-not $keys.hackathon) { throw "The function-specific API key could not be retrieved." }
$app = Invoke-Azure functionapp show --resource-group $ResourceGroup --name $appName --output json | ConvertFrom-Json
$hostName = $app.defaultHostName
if ($app.properties) { $hostName = $app.properties.defaultHostName }
if (-not $hostName) { throw "The Function App did not return its default hostname." }
$baseUrl = "https://$hostName/api"
$connection = [ordered]@{
    subscriptionId = $SubscriptionId
    resourceGroup = $ResourceGroup
    functionApp = $appName
    storageAccount = $storageName
    virtualNetwork = $vnetName
    baseUrl = $baseUrl
    openapiUrl = "$baseUrl/openapi.json"
    headerName = "x-functions-key"
    apiKey = $keys.hackathon
}
$connectionFile = Join-Path $local "connection.json"
$connection | ConvertTo-Json | Set-Content -LiteralPath $connectionFile -Encoding UTF8

$spec = Invoke-RestMethod -Uri "$baseUrl/openapi.json" -Method Get -TimeoutSec 120
$spec | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $local "openapi.json") -Encoding UTF8
Write-Host "OpenAPI: $baseUrl/openapi.json"
Write-Host "Orders:  $baseUrl/orders"
Write-Host "API key saved locally in $connectionFile (excluded from Git). Share it securely, not in source code."
Write-Host "Function-specific key: submit_order / hackathon. No real orders are stored or transmitted."
Write-Host "Storage stays private through blob/queue/table private endpoints. Private endpoints incur ongoing charges."
