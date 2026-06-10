/*
  main.bicepparam — production parameter values for Victros infrastructure.

  Sensitive values (aiKey) should be supplied via:
    az deployment group create ... --parameters aiKey="$(az keyvault secret show ...)"
  or injected from a CI pipeline secret — never committed to source control.

  Steps:
    1. Fill in entraTenantId and entraClientId from infra/entra/README.md
    2. Fill in aiEndpoint from your Azure AI resource
    3. Supply aiKey at deploy time (do not commit)
*/

using 'main.bicep'

param environment     = 'prod'
param location        = 'eastus2'

// From infra/entra/README.md — set after creating the External ID tenant
param entraTenantId   = '<YOUR_ENTRA_EXTERNAL_TENANT_ID>'
param entraClientId   = '<YOUR_ENTRA_CLIENT_ID>'

// Azure OpenAI capacity (thousands of tokens/min). Default 10 is fine for pilot.
// param aiCapacity = 10
