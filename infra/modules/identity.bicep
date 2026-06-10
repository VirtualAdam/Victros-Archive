/*
  identity.bicep
  User-assigned managed identity shared by the Container App.
  Used for:
    - Pulling images from ACR (AcrPull role)
    - Reading secrets from Key Vault (Key Vault Secrets User role)
    - Connecting to Cosmos DB (Cosmos DB Built-in Data Contributor role)
*/

param location string
param name string

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
}

output identityId string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId
