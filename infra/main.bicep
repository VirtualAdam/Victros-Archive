/*
  main.bicep — Victros production infrastructure
  ================================================
  Provisions all Azure resources for the Victros POC.

  Prerequisites (one-time manual steps):
    1. Create an Entra External ID tenant — see infra/entra/README.md
    2. Register the Victros app in that tenant — see infra/entra/README.md
    3. Create a resource group:
         az group create --name rg-victros-prod --location eastus2
    4. Deploy:
         az deployment group create \
           --resource-group rg-victros-prod \
           --template-file infra/main.bicep \
           --parameters infra/main.bicepparam

  Resources created:
    - User-assigned managed identity
    - Azure Container Registry (Basic)
    - Azure Cosmos DB (NoSQL, Session consistency)
    - Azure Key Vault (Standard)
    - Container Apps environment + backend app (with Easy Auth)
    - Azure Static Web Apps (Free tier)
    - Log Analytics workspace
*/

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Short environment tag used in all resource names (e.g. prod).')
@allowed(['prod'])
param environment string = 'prod'

@description('Cosmos DB database name.')
param cosmosDatabaseName string = 'victros'

@description('Container image tag to deploy.')
param imageTag string = 'latest'

@description('Entra External ID tenant ID (from infra/entra/README.md step 2).')
param entraTenantId string

@description('Entra External ID app registration client ID.')
param entraClientId string

@description('Azure OpenAI model deployment capacity in thousands of tokens per minute.')
param aiCapacity int = 10

@description('Comma-separated CORS origins for the backend (e.g. https://your-app.azurestaticapps.net). Leave empty on initial deploy; set after SWA is provisioned.')
param allowedOrigins string = ''

// ---------------------------------------------------------------------------
// Naming — all names derived from a single prefix for consistency
// ---------------------------------------------------------------------------

var prefix = 'victros-${environment}'
var identityName    = 'id-${prefix}'
var acrName         = replace('acr${prefix}', '-', '')   // ACR names: alphanumeric only
var cosmosName      = 'cosmos-${prefix}'
var kvName          = 'kv-${prefix}'
var caEnvName       = 'cae-${prefix}'
var caAppName       = 'ca-${prefix}-backend'
var swaName         = 'swa-${prefix}'
var aiName          = 'oai-${prefix}'

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    name: identityName
  }
}

module ai 'modules/ai.bicep' = {
  name: 'ai'
  params: {
    location: location
    name: aiName
  }
}

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    name: acrName
    identityPrincipalId: identity.outputs.principalId
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  params: {
    location: location
    accountName: cosmosName
    databaseName: cosmosDatabaseName
    identityPrincipalId: identity.outputs.principalId
  }
}

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault'
  params: {
    location: location
    name: kvName
    identityPrincipalId: identity.outputs.principalId
    cosmosConnectionString: cosmos.outputs.cosmosConnectionString
    aiEndpoint: ai.outputs.aiEndpoint
    aiKey: ai.outputs.aiKey
  }
}

module containerApps 'modules/container-apps.bicep' = {
  name: 'container-apps'
  params: {
    location: location
    environmentName: caEnvName
    appName: caAppName
    identityId: identity.outputs.identityId
    identityClientId: identity.outputs.clientId
    acrLoginServer: acr.outputs.acrLoginServer
    imageTag: imageTag
    cosmosSecretUri: keyVault.outputs.cosmosSecretUri
    aiEndpointSecretUri: keyVault.outputs.aiEndpointSecretUri
    aiKeySecretUri: keyVault.outputs.aiKeySecretUri
    entraClientId: entraClientId
    entraTenantId: entraTenantId
    // SWA URL added here after first deploy — update and redeploy
    allowedOrigins: ''
  }
}

module swa 'modules/swa.bicep' = {
  name: 'swa'
  params: {
    location: location
    name: swaName
    backendUrl: containerApps.outputs.backendUrl
    backendResourceId: containerApps.outputs.backendResourceId
    entraClientId: entraClientId
    entraTenantId: entraTenantId
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Backend API URL (Container Apps FQDN).')
output backendUrl string = containerApps.outputs.backendUrl

@description('Frontend URL (Static Web App hostname).')
output frontendUrl string = swa.outputs.swaUrl

@description('ACR login server — used in CI image push.')
output acrLoginServer string = acr.outputs.acrLoginServer

@description('ACR name — used in CI az acr build.')
output acrName string = acr.outputs.acrName

@description('Azure OpenAI endpoint.')
output aiEndpoint string = ai.outputs.aiEndpoint

@description('Azure OpenAI resource name.')
output aiName string = ai.outputs.aiName

@description('SWA deployment token — store as AZURE_STATIC_WEB_APPS_API_TOKEN in GitHub Actions.')
output swaDeploymentToken string = swa.outputs.deploymentToken
