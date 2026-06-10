/*
  swa.bicep
  Azure Static Web Apps — hosts the built React frontend.

  SWA provides:
    - Global CDN edge delivery
    - Managed SSL + custom domain
    - Built-in API proxy: /api/* → backend Container App URL
    - Easy Auth with Entra External ID (same app registration as backend)

  Deployment is handled by the swa CLI or GitHub Actions using the
  deployment token output here.

  Note: SWA Easy Auth and the linked backend URL are configured post-deploy
  via the Azure portal or `swa` CLI. The staticwebapp.config.json in the
  frontend repo controls routing rules and auth requirements.
*/

param location string
param name string
param backendUrl string           // Container Apps backend FQDN (https://...) — for output only
param backendResourceId string    // Full ARM resource ID of the Container App
param entraClientId string
param entraTenantId string

resource swa 'Microsoft.Web/staticSites@2025-03-01' = {
  name: name
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    stagingEnvironmentPolicy: 'Disabled'
    allowConfigFileUpdates: true
    // provider omitted — setting it to 'GitHub' without a wired repo causes deployment errors
  }
}

// Link the backend Container App as the SWA API backend.
// Requests to /api/* are proxied to the Container App.
resource linkedBackend 'Microsoft.Web/staticSites/linkedBackends@2025-03-01' = {
  parent: swa
  name: 'backend'
  properties: {
    backendResourceId: backendResourceId
    region: location
  }
}

output swaUrl string = 'https://${swa.properties.defaultHostname}'
output swaName string = swa.name
// Deployment token — store as AZURE_STATIC_WEB_APPS_API_TOKEN in the swa CLI deploy command
output deploymentToken string = swa.listSecrets().properties.apiKey
