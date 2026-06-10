# Victros Deployment Log

Live record of provisioned Azure resources.

**Subscription:** `<YOUR_SUBSCRIPTION_ID>` (Victros-Azure)
**Tenant:** `<YOUR_AZURE_TENANT_ID>`
**Region:** eastus2

---

## Resource Providers

Registered 2026-04-11:

| Provider | State |
|----------|-------|
| Microsoft.App | Registered |
| Microsoft.DocumentDB | Registered |
| Microsoft.ContainerRegistry | Registered |
| Microsoft.KeyVault | Registered |
| Microsoft.Web | Registered |
| Microsoft.ManagedIdentity | Registered |
| Microsoft.OperationalInsights | Registered |

---

## Resources

| Resource | Type | Name | Notes |
|----------|------|------|-------|
| Resource Group | `Microsoft.Resources/resourceGroups` | `rg-victros-prod` | Region: eastus2, provisioned 2026-04-11 |
| Service Principal | Azure AD App | `sp-victros-github` | App ID: `<YOUR_SERVICE_PRINCIPAL_APP_ID>`; Role: Owner on rg-victros-prod |
| Entra External ID Tenant | External tenant | `victros.onmicrosoft.com` | Tenant ID: `<YOUR_ENTRA_EXTERNAL_TENANT_ID>`; provisioned 2026-04-11 |
| Entra App Registration | App registration | `Victros` | Client ID: `<YOUR_ENTRA_CLIENT_ID>`; App role: `snapshot.generate`; ID tokens enabled |
| Managed Identity | `Microsoft.ManagedIdentity` | `id-victros-prod` | Shared identity for ACR pull, Key Vault, Cosmos access |
| Container Registry | `Microsoft.ContainerRegistry` | `acrvictrosprod` | Login server: `acrvictrosprod.azurecr.io`; backend image: `victros-backend:latest` |
| Cosmos DB | `Microsoft.DocumentDB` | `cosmos-victros-prod` | NoSQL; containers: sessions (/session_id), snapshots (/week_start) |
| Key Vault | `Microsoft.KeyVault` | `kv-victros-prod` | Stores cosmos connection string, AI endpoint + key |
| Azure OpenAI | `Microsoft.CognitiveServices` | `oai-victros-prod` | Endpoint: `https://<YOUR_OPENAI_ENDPOINT>.openai.azure.com/`; model: gpt-4o (10K TPM) |
| Log Analytics | `Microsoft.OperationalInsights` | `cae-victros-prod-logs` | Container App logs |
| Container Apps Env | `Microsoft.App/managedEnvironments` | `cae-victros-prod` | eastus2 |
| Container App | `Microsoft.App/containerApps` | `ca-victros-prod-backend` | URL: `https://<YOUR_CONTAINER_APP_FQDN>` |
| Static Web App | `Microsoft.Web/staticSites` | `swa-victros-prod` | URL: `https://<YOUR_SWA_HOSTNAME>.azurestaticapps.net`; Standard tier |

---

## GitHub Actions OIDC Federated Credentials

Configured on `sp-victros-github` (2026-04-11):

| Credential name | Subject |
|----------------|---------|
| `victros-main` | `repo:VirtualAdam/Victros-Archive:ref:refs/heads/main` |
| `victros-production-env` | `repo:VirtualAdam/Victros-Archive:environment:production` |

---

## GitHub Secrets Required

Add these at **GitHub → VirtualAdam/Victros-Archive → Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | `<YOUR_SERVICE_PRINCIPAL_APP_ID>` |
| `AZURE_TENANT_ID` | `<YOUR_AZURE_TENANT_ID>` |
| `AZURE_SUBSCRIPTION_ID` | `<YOUR_SUBSCRIPTION_ID>` |
| `AI_KEY` | _(your Azure AI Inference API key)_ |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | _(from Bicep deploy output — add after Step: Run Bicep)_ |

## GitHub Variables Required

Add these at **Settings → Secrets and variables → Actions → Variables tab**:

| Variable | Value |
|----------|-------|
| `AZURE_RESOURCE_GROUP` | `rg-victros-prod` |
| `ACR_NAME` | _(from Bicep deploy output)_ |
| `ACR_LOGIN_SERVER` | _(from Bicep deploy output)_ |
| `CONTAINER_APP_NAME` | _(from Bicep deploy output)_ |

---

## Pending

- [x] Add GitHub secrets (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID) — 2026-04-11
- [x] Add GitHub variable AZURE_RESOURCE_GROUP — 2026-04-11
- [x] Create `production` environment in GitHub repo settings — 2026-04-11
- [x] Create Entra External ID tenant `victros.onmicrosoft.com` — 2026-04-11
- [x] Register Victros app in External ID tenant — 2026-04-11
- [x] Fill in `infra/main.bicepparam` with Entra IDs — 2026-04-11
- [x] Run Bicep deploy — all resources provisioned 2026-04-12
- [x] GitHub variables set: ACR_NAME, ACR_LOGIN_SERVER, CONTAINER_APP_NAME — 2026-04-12
- [x] GitHub secret set: AZURE_STATIC_WEB_APPS_API_TOKEN — 2026-04-12
- [x] Deploy frontend to SWA — 2026-04-12
- [x] Update CORS with SWA URL — 2026-04-12
- [x] Add Entra redirect URIs — 2026-04-12
- [x] Assign `snapshot.generate` role to admin users in Entra — 2026-04-12
- [x] Smoke test: sign in via `https://<YOUR_SWA_HOSTNAME>.azurestaticapps.net` — 2026-04-12
