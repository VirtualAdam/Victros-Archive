/*
  key-vault.bicep
  Azure Key Vault — stores secrets referenced by the Container App.

  Secrets stored:
    cosmos-connection-string   — full Cosmos connection string (endpoint + key)
    victros-ai-endpoint        — Azure AI Inference endpoint URL
    victros-ai-key             — Azure AI Inference API key

  The managed identity is granted "Key Vault Secrets User" so the Container
  App can read secrets at runtime via secret references in the env config.
*/

param location string
param name string
param identityPrincipalId string
param cosmosConnectionString string
param aiEndpoint string

@secure()
param aiKey string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true   // RBAC model, not access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// Grant the Container App identity read access to secrets
var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identityPrincipalId, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource cosmosSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'cosmos-connection-string'
  properties: {
    value: cosmosConnectionString
  }
}

resource aiEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'victros-ai-endpoint'
  properties: {
    value: aiEndpoint
  }
}

resource aiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'victros-ai-key'
  properties: {
    value: aiKey
  }
}

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output cosmosSecretUri string = cosmosSecret.properties.secretUri
output aiEndpointSecretUri string = aiEndpointSecret.properties.secretUri
output aiKeySecretUri string = aiKeySecret.properties.secretUri
