# Victros — Complete Deployment Guide

This guide takes you from a fresh clone to a fully running Victros instance on Azure.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Create the Entra External ID Tenant](#3-create-the-entra-external-id-tenant)
4. [Register the Victros Application in Entra](#4-register-the-victros-application-in-entra)
5. [Configure Entra (Roles, User Flow, Admin Consent)](#5-configure-entra-roles-user-flow-admin-consent)
6. [Create the Azure Resource Group](#6-create-the-azure-resource-group)
7. [Register Required Resource Providers](#7-register-required-resource-providers)
8. [Deploy Infrastructure with Bicep](#8-deploy-infrastructure-with-bicep)
9. [Set Up GitHub Actions CI/CD (OIDC)](#9-set-up-github-actions-cicd-oidc)
10. [Configure GitHub Secrets and Variables](#10-configure-github-secrets-and-variables)
11. [Post-Deploy Wiring](#11-post-deploy-wiring)
12. [Deploy the Backend](#12-deploy-the-backend)
13. [Deploy the Frontend](#13-deploy-the-frontend)
14. [Verify the Deployment](#14-verify-the-deployment)
15. [Local Development Setup](#15-local-development-setup)
16. [Ongoing Operations](#16-ongoing-operations)
17. [Teardown](#17-teardown)

---

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Azure CLI | 2.60+ | Infrastructure provisioning |
| Node.js | 22+ | Frontend build |
| Python | 3.12+ | Backend |
| Git | any | Source control |
| GitHub CLI (`gh`) | 2.40+ | Optional — workflow monitoring |
| Docker (optional) | 24+ | Local development with Cosmos emulator |

You also need:
- An Azure subscription with **Owner** or **Contributor + User Access Administrator** permissions
- A GitHub account with admin access to the repository
- Access to create Entra External ID tenants (requires **Tenant Creator** role)

---

## 2. Clone the Repository

```bash
git clone https://github.com/VirtualAdam/Victros-Archive.git
cd Victros-Archive
```

---

## 3. Create the Entra External ID Tenant

The Entra External ID tenant provides user authentication (sign-up/sign-in) for the app.

> ⚠️ This step **must** be done in the Entra admin center, not the Azure portal.

1. Go to **https://entra.microsoft.com** and sign in with the account that owns your Azure subscription.

2. In the left nav → **Entra ID** → **Overview** → **Manage tenants**.

3. Click **+ Create** → select **External** → **Continue**.

4. Fill in the **Basics** tab:
   - **Tenant name**: `Victros`
   - **Domain name**: `victros` (becomes `victros.onmicrosoft.com` — must be globally unique)
   - **Location/Country**: `United States` (cannot be changed later)

5. If prompted for subscription:
   - **Subscription**: your target subscription
   - **Resource group**: create new → `rg-victros-entra`

6. Click **Review + create** → **Create**. Wait up to 30 minutes.

7. When complete, switch into the new tenant:
   - Click the **Settings** (gear) icon → **Directories + subscriptions**
   - Click **Switch** next to `victros.onmicrosoft.com`

8. Go to **Entra ID** → **Overview** and copy the **Tenant ID**.

   ```
   # Record this — needed in Step 8
   ENTRA_TENANT_ID=<your-tenant-id>
   ```

---

## 4. Register the Victros Application in Entra

> Make sure you are switched into the `victros` external tenant before proceeding.

1. Left nav → **Entra ID** → **App registrations** → **+ New registration**.

2. Fill in:
   - **Name**: `Victros`
   - **Supported account types**: Accounts in this organizational directory only
   - **Redirect URI**: leave blank (configured after infra deploy)

3. Click **Register**.

4. On the app **Overview** page, copy the **Application (client) ID**.

   ```
   # Record this — needed in Step 8
   ENTRA_CLIENT_ID=<your-client-id>
   ```

---

## 5. Configure Entra (Roles, User Flow, Admin Consent)

### 5a. Grant Admin Consent

1. From the app Overview → **API permissions** in the left menu.
2. Click **Grant admin consent for Victros** → **Yes** → **Refresh**.
3. Verify **Status** column shows **Granted for Victros**.

### 5b. Create the Snapshot Generator App Role

1. From the app Overview → **App roles** → **+ Create app role**.
2. Fill in:
   - **Display name**: `Snapshot Generator`
   - **Allowed member types**: Users/Groups
   - **Value**: `snapshot.generate`
   - **Description**: Can trigger weekly pipeline risk snapshot generation
3. Ensure **Enable this app role** is checked → **Apply**.

### 5c. Create the Sign-In User Flow

1. Left nav → **External Identities** → **User flows** → **+ New user flow**.
2. Fill in:
   - **Name**: `SignInSignUp`
   - **Identity providers**: Email with password
3. Under **User attributes**, check: **Email Address**, **Display Name**.
4. Click **Create**.

---

## 6. Create the Azure Resource Group

```bash
# Log into Azure (if not already)
az login

# Set the target subscription
az account set --subscription <your-subscription-id>

# Create the resource group
az group create \
  --name rg-victros-prod \
  --location eastus2
```

---

## 7. Register Required Resource Providers

These must be registered on the subscription before deploying:

```bash
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.DocumentDB
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.ManagedIdentity
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.CognitiveServices

# Wait for all to complete (takes 1-3 minutes)
az provider show --namespace Microsoft.App --query "registrationState" -o tsv
```

---

## 8. Deploy Infrastructure with Bicep

### 8a. Update Parameters

Edit `infra/main.bicepparam` with the values from Steps 3–4:

```bicep
using 'main.bicep'

param environment     = 'prod'
param location        = 'eastus2'

param entraTenantId   = '<ENTRA_TENANT_ID from Step 3>'
param entraClientId   = '<ENTRA_CLIENT_ID from Step 4>'
```

### 8b. Deploy

```bash
# Deploy all infrastructure (takes 5-10 minutes)
az deployment group create \
  --resource-group rg-victros-prod \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --query "properties.outputs" \
  --output json
```

### 8c. Record the Outputs

The deployment will output these values — save them all:

| Output | Example | Used For |
|--------|---------|----------|
| `backendUrl` | `https://ca-victros-prod-backend.<hash>.eastus2.azurecontainerapps.io` | Health checks, CORS |
| `frontendUrl` | `https://<YOUR_SWA_HOSTNAME>.azurestaticapps.net` | User access, CORS, Entra redirects |
| `acrLoginServer` | `acrvictrosprod.azurecr.io` | CI/CD variable |
| `acrName` | `acrvictrosprod` | CI/CD variable |
| `aiEndpoint` | `https://<YOUR_OPENAI_ENDPOINT>.openai.azure.com/` | Verification |
| `swaDeploymentToken` | `<long token>` | CI/CD secret |

---

## 9. Set Up GitHub Actions CI/CD (OIDC)

OIDC federated credentials allow GitHub Actions to authenticate to Azure without stored secrets.

### 9a. Create a Service Principal

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az ad sp create-for-rbac \
  --name sp-victros-github \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-victros-prod \
  --json-auth
```

Save the output — you need `appId` and `tenant`.

### 9b. Grant User Access Administrator (required for Bicep role assignments)

```bash
SP_APP_ID=<appId from above>

az role assignment create \
  --role "User Access Administrator" \
  --assignee $SP_APP_ID \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-victros-prod
```

### 9c. Add Federated Credentials

```bash
APP_OBJECT_ID=$(az ad app show --id $SP_APP_ID --query id -o tsv)

# Credential for pushes to main
az ad app federated-credential create \
  --id $APP_OBJECT_ID \
  --parameters '{
    "name": "victros-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:VirtualAdam/Victros-Archive:ref:refs/heads/main",
    "audiences": ["api://AzureADMultiTenantApp"]
  }'

# Credential for the production environment
az ad app federated-credential create \
  --id $APP_OBJECT_ID \
  --parameters '{
    "name": "victros-production-env",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:VirtualAdam/Victros-Archive:environment:production",
    "audiences": ["api://AzureADMultiTenantApp"]
  }'
```

---

## 10. Configure GitHub Secrets and Variables

Go to **GitHub → VirtualAdam/Victros-Archive → Settings → Secrets and variables → Actions**.

### Secrets tab

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | `appId` from Step 9a |
| `AZURE_TENANT_ID` | `tenant` from Step 9a (your **corp** tenant — NOT the External ID tenant) |
| `AZURE_SUBSCRIPTION_ID` | Your subscription ID |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | `swaDeploymentToken` from Step 8c |

### Variables tab

| Variable | Value |
|----------|-------|
| `AZURE_RESOURCE_GROUP` | `rg-victros-prod` |
| `ACR_NAME` | `acrName` from Step 8c (e.g., `acrvictrosprod`) |
| `ACR_LOGIN_SERVER` | `acrLoginServer` from Step 8c (e.g., `acrvictrosprod.azurecr.io`) |
| `CONTAINER_APP_NAME` | `ca-victros-prod-backend` |

### Create the Production Environment

Go to **Settings → Environments → New environment**:
- **Name**: `production`
- (Optional) Add required reviewers for manual approval before deploys

---

## 11. Post-Deploy Wiring

### 11a. Update CORS on the Container App

Re-run the Bicep deployment with the SWA URL as the allowed origin:

```bash
FRONTEND_URL="https://<your-swa-hostname>.azurestaticapps.net"

az deployment group create \
  --resource-group rg-victros-prod \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --parameters allowedOrigins="$FRONTEND_URL"
```

Or trigger via GitHub Actions: **Actions → Infrastructure — Deploy Bicep → Run workflow** with the `allowed_origins` input set.

### 11b. Configure Entra Redirect URIs

Switch back into the `victros` external tenant in the Entra portal:

1. Go to **Entra ID** → **App registrations** → **Victros** → **Authentication**.
2. Click **+ Add a platform** → **Web**.
3. Set **Redirect URI**: `https://<your-swa-hostname>.azurestaticapps.net/.auth/login/aad/callback`
4. Click **Configure**.
5. Under **Implicit grant and hybrid flows**, check **ID tokens** → **Save**.

### 11c. Configure SWA Auth Settings

In the Azure portal, navigate to the Static Web App resource:

1. Go to **Settings** → **Configuration** → **Application settings**.
2. Add:
   - `AAD_CLIENT_ID` = your `ENTRA_CLIENT_ID`
   - `AAD_CLIENT_SECRET` = create a client secret in the Entra app registration → **Certificates & secrets** → **+ New client secret** → copy the value here

### 11d. Update `staticwebapp.config.json` (if needed)

The file at `victros-poc/frontend/public/staticwebapp.config.json` contains the Entra tenant-specific OIDC issuer URL. Verify it matches your tenant:

```json
{
  "auth": {
    "identityProviders": {
      "azureActiveDirectory": {
        "registration": {
          "openIdIssuer": "https://victros.ciamlogin.com/<YOUR_ENTRA_TENANT_ID>/v2.0",
          "clientIdSettingName": "AAD_CLIENT_ID",
          "clientSecretSettingName": "AAD_CLIENT_SECRET"
        }
      }
    }
  }
}
```

If the domain name differs (e.g., you chose `victros-app` instead of `victros`), update the issuer URL accordingly: `https://<your-domain>.ciamlogin.com/<tenant-id>/v2.0`.

### 11e. Assign App Roles

1. In the Entra portal → **Enterprise applications** → find **Victros**.
2. Click **Users and groups** → **+ Add user/group**.
3. Select admin users → assign the **Snapshot Generator** role → **Assign**.

---

## 12. Deploy the Backend

### Option A: Via GitHub Actions (recommended)

Push any change to the `victros-poc/backend/` directory on `main`:

```bash
git push origin main
```

The workflow (`.github/workflows/backend.yml`) will:
1. Run unit tests (pytest)
2. Build the Docker image via ACR Tasks
3. Deploy to Container Apps

### Option B: Manual deploy via CLI

```bash
# From the repo root
./deploy.sh backend
```

This runs `az acr build` to build + push the image, then updates the Container App.

---

## 13. Deploy the Frontend

### Via GitHub Actions (only supported method)

Push any change to the `victros-poc/frontend/` directory on `main`:

```bash
git push origin main
```

The workflow (`.github/workflows/frontend.yml`) will:
1. Install dependencies (`npm ci`)
2. Build the React app (`npm run build`)
3. Deploy to Azure Static Web Apps

> ⚠️ **Do not use the SWA CLI** for deployment. It overwrites portal-managed auth configuration and breaks the OIDC flow. Always deploy via the GitHub Actions workflow.

---

## 14. Verify the Deployment

### Backend Health Check

```bash
BACKEND_URL=$(az containerapp show \
  --name ca-victros-prod-backend \
  --resource-group rg-victros-prod \
  --query "properties.configuration.ingress.fqdn" -o tsv)

curl -s "https://$BACKEND_URL/health" | python3 -m json.tool
```

Expected response:
```json
{
  "status": "ok",
  "version": "<git-sha>",
  "signals": 18
}
```

### Frontend Access

Open the SWA URL in a browser:
```
https://<your-swa-hostname>.azurestaticapps.net
```

You should be redirected to the Entra sign-in page. After signing in, you'll see the Victros start screen.

### End-to-End Smoke Test

1. Sign in at the frontend URL
2. Create a new session (enter an opportunity name)
3. Submit an intent (e.g., "I'm worried about losing this deal")
4. Confirm the situation validation
5. Complete intake fields (deal stage, offering type, etc.)
6. Confirm proposed signals
7. Verify a pattern diagnosis and strategy path are presented

---

## 15. Local Development Setup

### With Docker Compose (full stack + Cosmos emulator)

```bash
# Copy env file and fill in AI credentials
cp .env.example .env
# Edit .env: set VICTROS_AI_ENDPOINT and VICTROS_AI_KEY

# Start all services
docker compose up --build

# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
# Cosmos emulator: https://localhost:8081/_explorer/index.html
```

### Backend Only (file-based storage)

```bash
cd victros-poc
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run with file-based session storage (no Cosmos needed)
export STORAGE_BACKEND=file
export VICTROS_AI_ENDPOINT=https://your-resource.openai.azure.com/
export VICTROS_AI_KEY=

uvicorn server.main:create_app --factory --reload --port 8000
```

### Frontend Only

```bash
cd victros-poc/frontend
npm install
npm run dev
# Opens at http://localhost:5173 — proxies /api to localhost:8000
```

### Running Tests

```bash
cd victros-poc

# Backend unit tests (decision engine — no LLM needed)
pytest backend/tests -m "not llm and not integration" -q

# Frontend tests
cd frontend && npm test
```

---

## 16. Ongoing Operations

### CI/CD Pipeline Summary

| Event | Workflow | Action |
|-------|----------|--------|
| Push to `main` (backend changes) | [`.github/workflows/backend.yml`](.github/workflows/backend.yml) | Test → Build image → Deploy to Container Apps |
| Push to `main` (frontend changes) | [`.github/workflows/frontend.yml`](.github/workflows/frontend.yml) | Build → Deploy to SWA |
| Push to `main` (infra changes) | [`.github/workflows/deploy-infra.yml`](.github/workflows/deploy-infra.yml) | Validate → Deploy Bicep |
| Manual trigger | [`.github/workflows/deploy-infra.yml`](.github/workflows/deploy-infra.yml) | Deploy with custom image_tag or allowed_origins |
| Pull request | backend.yml / frontend.yml | Tests only — no deploy |

### Quick Manual Deploy (no CI/CD)

```bash
# Backend
./deploy.sh backend

# Frontend (must go through GitHub Actions)
git push origin main
```

### Monitoring

- **Container App logs**: Azure Portal → `ca-victros-prod-backend` → Monitoring → Log stream
- **Log Analytics queries**: Azure Portal → `cae-victros-prod-logs` → Logs
- **Cosmos DB metrics**: Azure Portal → `cosmos-victros-prod` → Metrics

### Scaling

The Container App auto-scales 1–3 replicas based on concurrent HTTP requests (threshold: 20). To adjust:

```bash
az containerapp update \
  --name ca-victros-prod-backend \
  --resource-group rg-victros-prod \
  --min-replicas 1 \
  --max-replicas 10
```

---

## 17. Teardown

To completely remove the deployment:

```bash
# Delete all Azure resources
az group delete --name rg-victros-prod --yes --no-wait

# Delete the Entra External ID tenant (from entra.microsoft.com)
# Entra ID → Manage tenants → select victros.onmicrosoft.com → Delete

# Remove the service principal
az ad app delete --id <SP_APP_ID>

# Remove GitHub secrets/variables manually from repo settings
```

---

## File Reference

| File | Purpose |
|------|---------|
| [`infra/main.bicep`](infra/main.bicep) | All Azure resources (identity, ACR, Cosmos, Key Vault, Container Apps, SWA, OpenAI) |
| [`infra/main.bicepparam`](infra/main.bicepparam) | Parameter values (Entra IDs, region) |
| [`infra/modules/`](infra/modules/) | Individual Bicep modules per service |
| [`infra/entra/README.md`](infra/entra/README.md) | Detailed Entra External ID setup instructions |
| [`.github/workflows/backend.yml`](.github/workflows/backend.yml) | Backend CI/CD (test → build → deploy) |
| [`.github/workflows/frontend.yml`](.github/workflows/frontend.yml) | Frontend CI/CD (build → deploy to SWA) |
| [`.github/workflows/deploy-infra.yml`](.github/workflows/deploy-infra.yml) | Infrastructure deployment (Bicep) |
| [`.github/CI_SETUP.md`](.github/CI_SETUP.md) | Detailed CI/CD setup reference |
| [`deploy.sh`](deploy.sh) | Manual backend deploy script (no CI needed) |
| [`docker-compose.yml`](docker-compose.yml) | Local dev stack (Cosmos emulator + backend + frontend) |
| [`.env.example`](.env.example) | Environment variables template |
| [`victros-poc/backend/Dockerfile`](victros-poc/backend/Dockerfile) | Backend container image |
| [`victros-poc/frontend/public/staticwebapp.config.json`](victros-poc/frontend/public/staticwebapp.config.json) | SWA auth + routing config |

---

## Architecture Quick Reference

```
                     Users
                       │
                       ▼
        Azure Static Web Apps (React SPA)
          │  Auth: Entra External ID
          │  Routes /api/* → linked backend
          ▼
     Azure Container Apps (FastAPI)
       │   Image from ACR
       │   Secrets from Key Vault
       │
       ├── Azure Cosmos DB (sessions, snapshots)
       └── Azure OpenAI GPT-4o (intent routing, extraction, explanation)
```

**Key principle**: The Decision Engine is pure Python — deterministic, no LLM. Only three services call GPT-4o (Intent Router, Extraction, Explanation), and none of them can alter strategic decisions.
