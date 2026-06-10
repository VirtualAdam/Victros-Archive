/*
  cosmos.bicep
  Azure Cosmos DB — NoSQL API account with two containers:
    sessions   — partition key /session_id
    snapshots  — partition key /week_start

  The managed identity is granted the built-in "Cosmos DB Built-in Data
  Contributor" role so the backend connects without a connection string key.
  The connection string (with key) is also stored in Key Vault for the
  initial SDK connection approach used in the current CosmosSessionRepository.
*/

param location string
param accountName string
param databaseName string
param identityPrincipalId string

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-02-15-preview' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    enableFreeTier: false
    publicNetworkAccess: 'Enabled'
    // Disable local auth (key-based) in favour of managed identity in a later
    // phase. Kept enabled for now because CosmosSessionRepository uses the
    // connection string SDK approach.
    disableLocalAuth: false
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-02-15-preview' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource sessionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'sessions'
  properties: {
    resource: {
      id: 'sessions'
      partitionKey: {
        paths: ['/session_id']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
      }
    }
    options: {
      throughput: 400
    }
  }
}

resource snapshotsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'snapshots'
  properties: {
    resource: {
      id: 'snapshots'
      partitionKey: {
        paths: ['/week_start']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
      }
    }
    options: {
      throughput: 400
    }
  }
}

// Cosmos DB Built-in Data Contributor role
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'
resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-02-15-preview' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, identityPrincipalId, cosmosDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    principalId: identityPrincipalId
    scope: cosmosAccount.id
  }
}

output cosmosAccountName string = cosmosAccount.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosAccountId string = cosmosAccount.id
