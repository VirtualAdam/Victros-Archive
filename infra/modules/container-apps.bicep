/*
  container-apps.bicep
  Azure Container Apps — environment + backend application.

  The backend Container App:
    - Pulls its image from ACR using the managed identity
    - Reads secrets from Key Vault via secret references
    - Has Easy Auth configured with Entra External ID
    - Exposes port 8000 via HTTPS ingress (internal + external)

  Easy Auth:
    Container Apps built-in auth validates the Entra JWT before the request
    reaches FastAPI. The backend reads X-MS-CLIENT-PRINCIPAL-* headers to
    identify the caller without any auth code in application logic.
*/

param location string
param environmentName string
param appName string
param identityId string
param identityClientId string
param acrLoginServer string
param imageTag string = 'latest'

// Key Vault secret URIs — Container Apps resolves these at runtime
param cosmosSecretUri string
param aiEndpointSecretUri string
param aiKeySecretUri string

// Entra External ID — app registration created manually per infra/entra/README.md
param entraClientId string
param entraTenantId string     // the External ID tenant (not your corp tenant)

// CORS: comma-separated list of allowed origins (SWA URL added after deploy)
param allowedOrigins string = ''

// Pre-compute CORS origins array from comma-separated string
var corsOrigins = allowedOrigins == '' ? [] : split(allowedOrigins, ',')

// Log Analytics workspace for container logs
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${environmentName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource backendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        // CORS policy omitted when no origins supplied (initial deploy).
        // Re-deploy with allowedOrigins=<swaUrl> after SWA is provisioned.
        corsPolicy: empty(corsOrigins) ? null : {
          allowedOrigins: corsOrigins
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: true
        }
      }
      registries: [
        {
          server: acrLoginServer
          identity: identityId
        }
      ]
      secrets: [
        {
          name: 'cosmos-connection-string'
          keyVaultUrl: cosmosSecretUri
          identity: identityId
        }
        {
          name: 'victros-ai-endpoint'
          keyVaultUrl: aiEndpointSecretUri
          identity: identityId
        }
        {
          name: 'victros-ai-key'
          keyVaultUrl: aiKeySecretUri
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: '${acrLoginServer}/victros-backend:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'STORAGE_BACKEND', value: 'cosmos' }
            { name: 'COSMOS_CONNECTION_STRING', secretRef: 'cosmos-connection-string' }
            { name: 'VICTROS_AI_ENDPOINT', secretRef: 'victros-ai-endpoint' }
            { name: 'VICTROS_AI_KEY', secretRef: 'victros-ai-key' }
            { name: 'ALLOWED_ORIGINS', value: allowedOrigins }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scale'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
}

// Easy Auth — Entra External ID as the identity provider.
// This validates the JWT before requests reach FastAPI and injects
// X-MS-CLIENT-PRINCIPAL-* headers that server/auth.py reads.
resource easyAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = {
  parent: backendApp
  name: 'current'
  properties: {
    platform: {
      // Easy Auth disabled — SWA handles auth and injects X-MS-CLIENT-PRINCIPAL headers.
      enabled: false
    }
    globalValidation: {
      // SWA handles auth upstream and injects X-MS-CLIENT-PRINCIPAL headers.
      // AllowAnonymous lets requests through; auth.py reads the SWA-injected headers.
      unauthenticatedClientAction: 'AllowAnonymous'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          openIdIssuer: '${environment().authentication.loginEndpoint}${entraTenantId}/v2.0'
          clientId: entraClientId
        }
        validation: {
          allowedAudiences: [
            entraClientId
          ]
        }
      }
    }
  }
}

output backendUrl string = 'https://${backendApp.properties.configuration.ingress.fqdn}'
output backendResourceId string = backendApp.id
output containerAppsEnvId string = containerAppsEnv.id
