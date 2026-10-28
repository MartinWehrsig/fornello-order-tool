# Fornello Order Tool

A shared HTTP tool for simulated pizza pickup orders. **One person deploys it
once; everyone else connects to the same API.** This repository contains only
the tool, its OpenAPI specification and deployment script.

## 1. Deploy once

You need Git, Azure CLI, PowerShell 5.1+ and an Azure subscription with permission
to create resources and role assignments (for example, Owner). Your organization
must allow the resources listed below. No local Python or Docker is required.

```powershell
git clone https://github.com/MartinWehrsig/fornello-order-tool.git
cd fornello-order-tool
az login
.\deploy.ps1 -SubscriptionId "<SUBSCRIPTION-ID>" -ResourceGroup "rg-pizza-team-swc"
```

The script deploys to **Sweden Central**, prints the endpoint URLs and saves:

| Local file | Purpose |
|---|---|
| `.local/connection.json` | Endpoint URLs and secret API key. Never publish or commit this file. |
| `.local/openapi.json` | OpenAPI specification with the deployed server URL. |

The first deployment can take several minutes. Running the same command again
updates the tool and preserves its existing API key.

## 2. Share the connection with your team

Give each team member:

- The **OpenAPI URL** printed by the script, or `.local/openapi.json`.
- The **API key**, shared separately through a secure channel.
- The authentication header name: **`x-functions-key`**.
- The [menu](menu.txt), if they need item codes, sizes and prices.

Team members import the specification into an OpenAPI-compatible client and
configure the API key as a header. Alternatively, call `POST {baseUrl}/orders`
directly. `GET {baseUrl}/openapi.json` is public; submitting an order requires
the key. The deployed specification contains the correct base URL.

**No separate deployment or tool programming is needed for other team members.**

## 3. Test the tool

From the deployment directory, submit a large Margherita with extra mushrooms:

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

Expected: `status: accepted_demo`, a `DEMO-...` order ID, `total_eur: "12.40"`
and an English confirmation explicitly stating that no real order was placed.

Optional: `python verify_live_api.py` checks authentication, pricing and invalid
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

This is a demo tool, not a production ordering system.
