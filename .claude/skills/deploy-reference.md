# Victros Deployment Reference

This file contains all commands, values, and configuration details needed to deploy Victros to Azure. Used by the deploy skill as a reference — do not send this to the user directly.

---

## Architecture

```
Users → Azure Static Web Apps (React SPA, Entra External ID auth)
         → Azure Container Apps (FastAPI backend)
              → Azure Cosmos DB (sessions, snapshots)
              → Azure OpenAI GPT-4o (intent routing, extraction, explanation)
```

Key resources created by Bicep:
- Resource Group: `rg-victros-prod`
- Container App: `ca-victros-prod-backend`
- Container App Environment: `cae-victros-prod`
- Container Registry: `acrvictrosprod`
- Cosmos DB: `cosmos-victros-prod`
- Key Vault: `kv-victros-prod`
- Static Web App: `swa-victros-prod`
- Azure OpenAI: `oai-victros-prod`
- Managed Identity: `id-victros-prod-backend`

---

## Phase 1: Environment Setup Commands

### Detect OS and Install Missing Tools

```bash
# Detect OS
uname -s  # Darwin = macOS, Linux = Linux
# On Windows, check: $env:OS or systeminfo

# --- macOS (Homebrew) ---
# Install Homebrew if missing:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install git
brew install azure-cli
brew install node@22
brew install python@3.12

# --- Linux (Ubuntu/Debian) ---
sudo apt-get update
sudo apt-get install -y git python3.12 python3.12-venv
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# --- Windows (winget) ---
winget install Git.Git
winget install Microsoft.AzureCLI
winget install OpenJS.NodeJS --version 22
winget install Python.Python.3.12
```

### Verify Installations

```bash
git --version                   # Any version
az --version | head -1          # Need 2.60+
node --version                  # Need 22+
python3 --version               # Need 3.12+
```

### Clone and Login

```bash
git clone https://github.com/VirtualAdam/Victros-Archive.git
cd Victros-Archive

az login
az account show --query '{subscription:name, id:id, user:user.name}' -o table
```

---

## Phase 2: Entra External ID — Human Instructions

### Step 2a: Create External ID Tenant

Instruct user:
1. Go to https://entra.microsoft.com
2. Left nav → Entra ID → Overview → Manage tenants
3. Click + Create → External → Continue
4. Tenant name: `Victros`
5. Domain name: `victros` (must be globally unique — try alternatives if taken)
6. Location: `United States`
7. Subscription: their target subscription
8. Resource group: create new → `rg-victros-entra`
9. Review + Create → Create (wait up to 30 minutes)
10. Switch into the new tenant: Settings (gear) → Directories + subscriptions → Switch
11. Copy the Tenant ID from Entra ID → Overview

Ask user for: **ENTRA_TENANT_ID**

### Step 2b: Register Application

Instruct user (must be switched into the victros external tenant):
1. Left nav → Entra ID → App registrations → + New registration
2. Name: `Victros`
3. Supported account types: Accounts in this organizational directory only
4. Redirect URI: leave blank (configured later)
5. Click Register
6. Copy the Application (client) ID from Overview

Ask user for: **ENTRA_CLIENT_ID**

### Step 2c: Grant Admin Consent

Instruct user:
1. From app Overview → API permissions
2. Click "Grant admin consent for Victros" → Yes → Refresh
3. Verify Status shows "Granted for Victros"

### Step 2d: Create App Role

Instruct user:
1. From app Overview → App roles → + Create app role
2. Display name: `Snapshot Generator`
3. Allowed member types: Users/Groups
4. Value: `snapshot.generate`
5. Description: `Can trigger weekly pipeline risk snapshot generation`
6. Ensure "Enable this app role" is checked → Apply

### Step 2e: Create User Flow

Instruct user:
1. Left nav → External Identities → User flows → + New user flow
2. Name: `SignInSignUp`
3. Identity providers: Email with password
4. User attributes: check Email Address, Display Name
5. Click Create

---

## Phase 3: Azure Infrastructure Commands

### 3a: Resource Group

```bash
az group create --name rg-victros-prod --location eastus2
```

### 3b: Resource Providers

```bash
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.DocumentDB
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.ManagedIdentity
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.CognitiveServices

# Poll until all registered (loop or check individually)
for ns in Microsoft.App Microsoft.DocumentDB Microsoft.ContainerRegistry Microsoft.KeyVault Microsoft.Web Microsoft.ManagedIdentity Microsoft.OperationalInsights Microsoft.CognitiveServices; do
  state=$(az provider show --namespace $ns --query "registrationState" -o tsv)
  echo "$ns: $state"
done
```

### 3c: Update Bicep Parameters

Edit `infra/main.bicepparam`:
```bicep
param entraTenantId   = '<ENTRA_TENANT_ID>'
param entraClientId   = '<ENTRA_CLIENT_ID>'
```

### 3d: Deploy Bicep

```bash
az deployment group create \
  --resource-group rg-victros-prod \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --query "properties.outputs" \
  --output json
```

Expected outputs to capture:
- `backendUrl` — Container App FQDN
- `frontendUrl` — Static Web App hostname
- `acrLoginServer` — e.g., `acrvictrosprod.azurecr.io`
- `acrName` — e.g., `acrvictrosprod`
- `aiEndpoint` — Azure OpenAI endpoint URL
- `swaDeploymentToken` — needed for GitHub secret

---

## Phase 4: Post-Deploy Wiring

### 4a: Update CORS (Automated)

```bash
FRONTEND_URL="<frontendUrl from Bicep output>"

az deployment group create \
  --resource-group rg-victros-prod \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --parameters allowedOrigins="$FRONTEND_URL"
```

### 4b: Entra Redirect URIs (Human)

Instruct user — switch into victros external tenant:
1. Entra ID → App registrations → Victros → Authentication
2. + Add a platform → Web
3. Redirect URI: `<frontendUrl>/.auth/login/aad/callback`
4. Click Configure
5. Under "Implicit grant and hybrid flows", check ID tokens → Save

### 4c: SWA Auth Settings (Human)

Instruct user — in Azure portal:
1. Navigate to Static Web App `swa-victros-prod`
2. Settings → Configuration → Application settings
3. Add: `AAD_CLIENT_ID` = the ENTRA_CLIENT_ID value
4. Add: `AAD_CLIENT_SECRET` = create new client secret in Entra app → Certificates & secrets → + New client secret → copy value
5. Save

### 4d: Verify staticwebapp.config.json (Automated)

File: `victros-poc/frontend/public/staticwebapp.config.json`

The `openIdIssuer` must be: `https://<domain>.ciamlogin.com/<ENTRA_TENANT_ID>/v2.0`

Default domain is `victros`. If different, update the file and commit.

---

## Phase 5: Deploy Application

### Backend

```bash
./deploy.sh backend
```

### Frontend

Build and deploy directly using the SWA deployment token:

```bash
cd victros-poc/frontend
npm ci
npm run build

# Install SWA CLI and deploy
npx @azure/static-web-apps-cli deploy ./dist \
  --deployment-token "<swaDeploymentToken from Bicep output>" \
  --env production
```

**WARNING**: After auth is configured in Phase 4 (SWA app settings), using the SWA CLI for subsequent deploys may overwrite portal-managed auth config. For future deploys, consider setting up CI/CD (see deployment-guide.md Steps 9-10) or re-apply auth settings after each CLI deploy.

---

## Phase 6: Verification

### Backend Health

```bash
BACKEND_URL=$(az containerapp show \
  --name ca-victros-prod-backend \
  --resource-group rg-victros-prod \
  --query "properties.configuration.ingress.fqdn" -o tsv)

curl -s "https://$BACKEND_URL/health" | python3 -m json.tool
```

Expected: `{"status": "ok", "version": "<sha>", "signals": 18}`

### Frontend

Open in browser: `<frontendUrl>`
- Should redirect to Entra sign-in
- After sign-in, should show Victros start screen

### Smoke Test Checklist

1. Sign in at frontend URL
2. Create a new session (enter opportunity name)
3. Submit an intent (e.g., "I'm worried about losing this deal")
4. Confirm the situation validation
5. Complete intake fields (deal stage, offering type, etc.)
6. Confirm proposed signals
7. Verify pattern diagnosis and strategy path are presented

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Bicep deploy fails with provider error | Resource provider not registered | Re-run `az provider register` and wait |
| GitHub Actions OIDC login fails | Wrong tenant ID in secrets (must be corp tenant, not External ID) | Update AZURE_TENANT_ID secret |
| Frontend shows 403 after login | Redirect URI mismatch | Check exact URL in Entra matches SWA hostname |
| Backend returns 500 | Missing AI key or Cosmos connection | Check Container App env vars via `az containerapp show` |
| Auth loop / infinite redirect | staticwebapp.config.json issuer URL wrong | Verify domain and tenant ID in issuer |
| SWA deploy breaks auth | Deployed with SWA CLI instead of GitHub Actions | Redeploy via Actions; reconfigure auth in portal |
