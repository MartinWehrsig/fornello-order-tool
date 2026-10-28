# Fornello Order Tool

HTTP API for simulated pizza pickup orders.

## Deployment

Prerequisites: Git, Azure CLI, PowerShell 5.1+ and Azure permissions to create
resources and role assignments (for example, Owner).

```powershell
git clone https://github.com/MartinWehrsig/fornello-order-tool.git
cd fornello-order-tool
az login
.\deploy.ps1 -SubscriptionId "<SUBSCRIPTION-ID>" -ResourceGroup "rg-pizza-team-swc"
```

Region: **Sweden Central**. Outputs:

| Local file | Purpose |
|---|---|
| `.local/connection.json` | Endpoint URLs and secret API key. Never publish or commit this file. |
| `.local/openapi.json` | OpenAPI specification with the deployed server URL. |

Redeployment preserves the existing API key.

## Connection

- `GET {baseUrl}/openapi.json`: public specification with the deployed server URL.
- `POST {baseUrl}/orders`: submit an order; requires the `x-functions-key` header.
- API key: `.local/connection.json`; distribute through a secure channel.
- [Menu](menu.txt): item codes, sizes and prices.

## Test

Large Margherita with extra mushrooms:

```powershell
$connection = Get-Content .\.local\connection.json -Raw | ConvertFrom-Json
$headers = @{ "x-functions-key" = $connection.apiKey }
$body = @{
    confirmed = $true
    items = @(@{
        item_code = "P01"; size = "large"; quantity = 1
        extra_toppings = @("mushrooms"); variant = ""
    })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "$($connection.baseUrl)/orders" `
    -Headers $headers -ContentType "application/json" -Body $body
```

Expected: `status: accepted_demo`, a `DEMO-...` order ID and `total_eur: "12.40"`.

`python verify_live_api.py` checks authentication, pricing and invalid
requests against the deployment. Requires Python 3.10+, no extra packages.

## Scope and costs

- 39 menu items, pizza sizes and up to five distinct extra toppings per pizza.
- Demo pickup only: no real restaurant connection, storage, payments, delivery,
  discounts, special dough, substitutions or half-and-half pizzas.
- `confirmed=true` is required. The stateless API cannot verify actual human
  consent; callers must obtain it before submitting. Each successful request
  generates a new demo ID, so do not automatically retry submissions.
- Infrastructure: Azure Function/Flex plan, private Storage, managed identity,
  VNet and three private endpoints for Blob/Queue/Table. The HTTPS API is public;
  Storage has public network access and Shared Key disabled. Private DNS is global.
- Function/Storage usage charges and **ongoing charges for three private endpoints,
  even when idle**. No Application Insights is created.
- When finished, delete the dedicated resource group in the Azure portal after
  checking that it contains no resources needed by other applications.
