/*
  ai.bicep
  Azure OpenAI resource + gpt-4o model deployment.

  The backend reads VICTROS_AI_ENDPOINT and VICTROS_AI_KEY from Key Vault.
  This module outputs both so main.bicep can store them there.

  Model: gpt-4o (standard deployment, pay-as-you-go capacity)
  Capacity: 10K tokens/minute — sufficient for the POC pilot.
  Increase capacity or switch to provisioned throughput when scaling.

  Note: Azure OpenAI availability varies by region. eastus2 supports gpt-4o.
*/

param location string
param name string

resource openAI 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAI
  name: 'gpt-4o'
  sku: {
    name: 'Standard'
    capacity: 10   // 10K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

output aiEndpoint string = openAI.properties.endpoint
output aiName string = openAI.name
// Key returned as a secure value for Key Vault storage — not logged
output aiKey string = openAI.listKeys().key1
