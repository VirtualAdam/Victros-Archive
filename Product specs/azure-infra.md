# Victros — Azure Cloud Infrastructure Design

## Overview

This document maps the Victros POC architecture onto Azure services. The design follows
the product's core principle: a deterministic decision engine with a conversational UI,
supported by constrained LLM calls for extraction, routing, and explanation.

The design is organized into five layers: edge and delivery, compute, AI, data, and
security. Components are sized for a POC/early-production workload with a clear path
to scale.

---

## Architecture Diagram

```
                         ┌──────────────────────────────────────────────┐
                         │              External Users                   │
                         └──────────────────┬───────────────────────────┘
                                            │ HTTPS
                                            ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                          Azure Front Door (Premium)                            │
│                                                                                │
│  ┌─────────────┐   ┌────────────────┐   ┌─────────────────────────────────┐  │
│  │  WAF Policy  │   │  Custom Domain  │   │  Origin Groups                  │  │
│  │  (OWASP 3.2) │   │  + TLS/HTTPS   │   │  /api/* → Container Apps        │  │
│  └─────────────┘   └────────────────┘   │  /*    → Static Web App          │  │
│                                          └─────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
           │                                          │
           │ /api/*                                   │ /* (static assets)
           ▼                                          ▼
┌──────────────────────────────┐          ┌──────────────────────┐
│  Azure Container Apps         │          │  Azure Static         │
│  Environment (VNet-injected)  │          │  Web Apps             │
│                               │          │                       │
│  ┌────────────────────────┐   │          │  React SPA            │
│  │   victros-api           │   │          │  Built via GitHub     │
│  │   (FastAPI)             │   │          │  Actions → deployed   │
│  │                         │   │          │  on merge to main     │
│  │  • Intent Router        │   │          └──────────────────────┘
│  │  • Ingestion Layer      │   │
│  │  • Extraction Service   │   │
│  │  • Decision Engine      │   │
│  │  • Explanation Service  │   │
│  │  • Confirmation Gate    │   │
│  │  • Session Manager      │   │
│  │  • Readiness Check      │   │
│  │                         │   │
│  │  Min: 1  Max: 10        │   │
│  │  Scale: concurrent req  │   │
│  └──────────┬──────────────┘   │
│             │                  │
└─────────────┼──────────────────┘
              │ Private Endpoints (VNet)
              │
    ┌─────────┼───────────────────────────────────────┐
    │         │                                       │
    │  ┌──────▼────────────┐   ┌──────────────────┐  │
    │  │  Azure AI Foundry  │   │  Azure Cosmos DB  │  │
    │  │  (Model Endpoint)  │   │  (NoSQL API)      │  │
    │  │                   │   │                  │  │
    │  │  Deployment:      │   │  Containers:     │  │
    │  │  GPT-4o           │   │  • sessions      │  │
    │  │                   │   │  • schema        │  │
    │  │  Used by:         │   │  • evaluations   │  │
    │  │  • Intent Router  │   │  • attachments   │  │
    │  │  • Extraction Svc │   │    (metadata)    │  │
    │  │  • Explanation Svc│   │  • audit_events  │  │
    │  │                   │   │  • users         │  │
    │  │  Token logging:   │   │  • tenants       │  │
    │  │  App Insights     │   │                  │  │
    │  └───────────────────┘   └──────────────────┘  │
    │                                                 │
    │  ┌──────────────────────┐  ┌─────────────────┐  │
    │  │  Azure Blob Storage   │  │  Azure Key Vault │  │
    │  │                       │  │                  │  │
    │  │  Containers:          │  │  Secrets:        │  │
    │  │  • attachments        │  │  • AI Foundry    │  │
    │  │    (user uploads)     │  │    endpoint key  │  │
    │  │  • schema-static      │  │  • Cosmos DB     │  │
    │  │    (JSON backups)     │  │    connection    │  │
    │  │  • exports            │  │  • Blob SAS key  │  │
    │  │                       │  │  • JWKS signing  │  │
    │  │  Lifecycle policy:    │  │    key           │  │
    │  │  attachments → 90d    │  │                  │  │
    │  │  exports → 30d        │  │  All accessed    │  │
    │  └──────────────────────┘  │  via Managed     │  │
    │                            │  Identity (no    │  │
    │                            │  secrets in env) │  │
    │                            └─────────────────┘  │
    └─────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│           Observability (cross-cutting)               │
│                                                       │
│  Azure Monitor ← Log Analytics Workspace             │
│       ↑               ↑              ↑               │
│  Container Apps   AI Foundry     Cosmos DB           │
│  (structured      (token usage,  (request units,     │
│   access logs,    latency,       errors)             │
│   trace IDs)      errors)                            │
│                                                       │
│  Application Insights SDK in FastAPI                  │
│  → traces every LLM call with:                       │
│    session_id, state, component, input_tokens,       │
│    output_tokens, latency_ms                         │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│           CI/CD                                       │
│                                                       │
│  GitHub Actions                                       │
│  ├── build + test (pytest decision engine)           │
│  ├── push image → Azure Container Registry           │
│  ├── deploy revision → Container Apps               │
│  └── deploy → Static Web Apps                       │
│                                                       │
│  Azure Container Registry                            │
│  └── victros-api:sha-{commit}                       │
└──────────────────────────────────────────────────────┘
```

---

## Component Guide

### Edge: Azure Front Door Premium

| Property | Value |
|---|---|
| SKU | Premium (required for private link origin) |
| WAF Policy | OWASP 3.2, prevention mode |
| Custom domain | victros.ai / api.victros.ai |
| TLS | Front Door-managed, min TLS 1.2 |
| Origin: SPA | Azure Static Web App |
| Origin: API | Container Apps environment ingress |
| Routing | Path-based: `/api/*` → Container Apps, `/*` → Static Web App |
| Caching | Disabled for `/api/*`, enabled for static assets |

Front Door is the single published entry point. No component behind it is directly
internet-accessible. Container Apps ingress is internal-only with the VNet.

---

### Frontend: Azure Static Web Apps

| Property | Value |
|---|---|
| Framework | React (TypeScript) |
| Deploy trigger | GitHub Actions on merge to `main` |
| Environment variables | Injected at build time (no secrets) |
| Auth | Delegates entirely to backend JWT validation |
| CDN | Built-in global CDN via Front Door |

The React SPA is a static build. All application state lives in the backend. The
frontend calls the FastAPI endpoints and renders what the server returns. No schema
data is shipped to the client beyond what the API returns per request.

---

### Compute: Azure Container Apps

| Property | Value |
|---|---|
| Environment | VNet-injected (internal ingress only) |
| App name | `victros-api` |
| Image | `victros.azurecr.io/victros-api:{sha}` |
| Min replicas | 1 |
| Max replicas | 10 |
| Scale rule | HTTP concurrent requests (threshold: 20) |
| CPU | 0.5 vCPU (scale to 2.0 under load) |
| Memory | 1 GiB (scale to 4 GiB under load) |
| Identity | System-assigned Managed Identity |
| Secrets | All loaded from Key Vault via Managed Identity at startup |
| Health probe | `GET /health` — returns 200 when schema loaded |

The Decision Engine runs as an in-process Python module — no separate container needed.
The schema JSON files are either bundled in the container image (simplest for POC) or
loaded from Blob Storage at startup and cached in memory.

**Session-affinity note:** Container Apps does not provide sticky sessions by default.
Because session state lives in Cosmos DB (not in-process memory), any replica can
serve any request. No sticky session configuration is needed.

---

### AI: Azure AI Foundry

| Property | Value |
|---|---|
| Model | GPT-4o (or GPT-4.1 if available) |
| Deployment type | Standard deployment |
| Region | Match primary Cosmos DB region |
| Access | Managed Identity or API key (Key Vault) |
| Content filter | Default — escalate if legal requires adjustments |
| Logging | Diagnostic logs → Log Analytics |

Three components call the LLM. Each uses a distinct prompt template loaded from
`/prompts/` at startup:

| Component | Prompt file | Max tokens (approx) |
|---|---|---|
| Intent Router | `intent_router.txt` | 200 |
| Extraction Service | `extraction.txt` | 1 000 |
| Explanation Service | `explanation.txt` | 1 500 |

The Decision Engine never calls the LLM. Only the three services above do.

Application Insights traces each call with `session_id`, `component`, and token counts
so cost and latency per session state can be monitored.

---

### Data: Azure Cosmos DB (NoSQL API)

| Property | Value |
|---|---|
| API | NoSQL (document model matches existing session JSON) |
| Consistency | Session (strong reads within a session, relaxed cross-doc) |
| Regions | Single-region for POC; add read replica when needed |
| Throughput | Autoscale (400–4 000 RU/s for POC) |
| Partition strategy | See container table below |
| Backup | Continuous (7-day restore point) |
| Private access | Private endpoint in Container Apps VNet |

**Container design:**

| Container | Partition key | What lives here |
|---|---|---|
| `sessions` | `/tenant_id` | Full session document: signals, patterns, strategy path, lever states, deal snapshot, interaction history |
| `schema` | `/schema_type` | Static schema documents: signals, patterns, strategy_paths, levers, zones, representative_actions — loaded at startup, refreshed on deploy |
| `evaluation_log` | `/tenant_id` | Append-only record of every Decision Engine run: timestamp, session_id, input signals, output pattern, strategy path |
| `audit_events` | `/tenant_id` | Authentication, signal confirmations, state transitions, exports, deletions — immutable once written |
| `users` | `/tenant_id` | User profile, role, team membership |
| `tenants` | `/id` | Tenant configuration, feature flags, retention policy |
| `attachments` | `/tenant_id` | Metadata record per upload: blob reference, extraction status, extraction outputs — not the raw file |

Raw attachment files live in Blob Storage. Cosmos DB holds only the metadata record and
the structured extraction outputs. This keeps document size bounded and allows blob-level
retention policies to operate independently.

---

### Storage: Azure Blob Storage

| Property | Value |
|---|---|
| Account type | StorageV2, LRS for POC |
| Access | Managed Identity from Container Apps |
| Private access | Private endpoint |

| Container | Contents | Retention |
|---|---|---|
| `attachments` | Uploaded CRM screenshots, PDFs, CSVs | 90 days, then auto-delete |
| `attachments-extracted` | LLM extraction outputs stored as JSON alongside source | Same lifecycle as source |
| `schema-static` | JSON schema file backups (versioned) | Indefinite |
| `session-exports` | User-triggered session exports | 30 days |

Blob naming: `{tenant_id}/{session_id}/{upload_id}/{original_filename}` — keeps tenant
data segregated at the object level without requiring separate accounts.

---

### Security: Azure Key Vault

| Property | Value |
|---|---|
| SKU | Standard (Premium if HSM-backed keys needed later) |
| Access model | RBAC (not legacy access policies) |
| Access grants | Container Apps Managed Identity: secrets/get |
| Private access | Private endpoint |

Secrets stored:

| Secret name | Contents |
|---|---|
| `ai-foundry-endpoint` | AI Foundry endpoint URL |
| `ai-foundry-key` | AI Foundry API key (rotate every 90 days) |
| `cosmos-connection` | Cosmos DB primary connection string |
| `blob-connection` | Storage account connection string |
| `jwt-signing-key` | HMAC key for session token signing (POC auth) |

No secret appears in container environment variables or source code. All are resolved at
runtime via the Azure Key Vault SDK using Managed Identity.

---

### Identity: Managed Identity and Auth

**Service-to-service (infrastructure):**
All Azure services communicate via System-assigned Managed Identity on the
Container Apps app. No stored credentials in environment variables.

**User authentication (POC):**
For the initial POC, simple JWT-based auth is sufficient:
- User presents email/password or magic link
- FastAPI issues a signed JWT (key in Key Vault)
- JWT carries `user_id`, `tenant_id`, `role`
- All session, evaluation, and audit documents are scoped to `tenant_id`

**Future enterprise auth path (ready to add, not required now):**
- Replace local JWT with Entra ID / Azure AD B2C
- Add SCIM provisioning endpoint
- Manager role gets read access to subordinate sessions within same `tenant_id`

The session and audit data model uses `tenant_id` and `user_id` from day one, so
adding enterprise identity later does not require a data migration.

---

### Observability: Azure Monitor + Application Insights

| Signal | Source | Destination | Notes |
|---|---|---|---|
| Container Apps access logs | Container Apps diagnostic settings | Log Analytics | All HTTP requests, status codes |
| Application traces | App Insights SDK in FastAPI | App Insights | Per-request traces with session_id, state, component |
| LLM call telemetry | Custom trace in each LLM service | App Insights | component, session_id, state, input_tokens, output_tokens, latency_ms |
| Decision Engine runs | evaluation_log container | Cosmos DB | Append-only — not App Insights, for query and learning |
| Cosmos DB metrics | Cosmos DB diagnostic settings | Log Analytics | RU consumption, throttling, latency |
| AI Foundry usage | AI Foundry diagnostic settings | Log Analytics | Token usage, content filter results |
| Key Vault access | Key Vault diagnostic settings | Log Analytics | Secret access audit |

Alerts to configure from day one:
- Container Apps: HTTP 5xx rate > 1% over 5 minutes
- AI Foundry: latency > 10s (indicates timeout risk)
- Cosmos DB: throttled requests > 0 (means RU budget too low)
- Key Vault: any denied secret access

---

### CI/CD: GitHub Actions + Azure Container Registry

```
Push to feature branch
    └── lint, type-check, unit tests (pytest decision engine fixtures)

Merge to main
    ├── build Docker image
    ├── push to ACR as victros-api:sha-{commit}
    ├── deploy new revision to Container Apps (traffic split: 10% new, 90% old)
    ├── smoke test /health and /api/schema/signals
    └── shift to 100% on pass (or rollback on fail)

Static Web App deploy runs in parallel with backend deploy.
```

The Decision Engine unit tests (test_decision_engine.py, test_pattern_collision.py,
test_signal_activation.py) run on every commit. A failed Decision Engine test blocks
deploy. This is the primary correctness gate for the deterministic core.

---

## Network Topology Summary

```
Internet
    │
    ▼
Azure Front Door (public, WAF)
    │
    ├── → Azure Static Web Apps (public origin, Front Door-managed)
    │
    └── → Container Apps Environment (VNet, internal ingress only)
              │
              ├── Private Endpoint → Cosmos DB
              ├── Private Endpoint → Blob Storage
              ├── Private Endpoint → Key Vault
              └── Private Endpoint → AI Foundry endpoint
```

No component in the data layer has a public endpoint. All access from the Container
Apps workload goes through private endpoints inside the VNet.

---

## Environment Strategy

| Environment | Purpose | Scale | Notes |
|---|---|---|---|
| `dev` | Developer local + PR validation | Container Apps min 1 | Shared Cosmos DB with `dev` prefix on containers |
| `staging` | Pre-prod integration, demo runs | Same infra as prod, smaller autoscale max | Uses prod schema, synthetic sessions only |
| `prod` | Live user workload | Full autoscale | Real customer data, full audit logging |

Schema JSON is version-controlled and deployed as part of the container image. Schema
changes follow the same PR and review process as code changes.

---

## Sizing and Cost Guidance (POC)

| Service | SKU / Tier | Estimated monthly cost |
|---|---|---|
| Azure Front Door | Premium | ~$350 (base) |
| Azure Static Web Apps | Free tier | $0 |
| Azure Container Apps | Consumption plan, 1–10 replicas | ~$50–200 depending on load |
| Azure Container Registry | Basic | ~$5 |
| Azure AI Foundry (GPT-4o) | Pay-per-token | ~$50–500 depending on usage |
| Azure Cosmos DB | Autoscale 400–4 000 RU/s | ~$25–50 |
| Azure Blob Storage | LRS, < 100 GB | ~$5 |
| Azure Key Vault | Standard | ~$5 |
| Azure Monitor / App Insights | Pay-per-GB, low volume | ~$20 |
| **Total estimate (POC)** | | **~$500–1 200 / month** |

AI Foundry token cost dominates at scale. The three LLM call types (routing,
extraction, explanation) should each be benchmarked against expected session volume
early to identify the primary cost driver.

---

## Open Infrastructure Questions (maps to build-spec-questions.md)

These decisions affect the design above but depend on answers from the stakeholder meeting:

| Question | Impact on design |
|---|---|
| Enterprise SSO required from day one? | Replace JWT auth with Entra ID; add B2C tenant or federated OIDC |
| Sessions shared across a team? | Add team membership to users container; add session-level ACL |
| Customer data allowed in hosted LLM API? | If no, requires private Azure OpenAI deployment per tenant, higher cost |
| FedRAMP required later? | Requires IL2/IL4 region, separate Entra tenant, US-person support constraint |
| Customer-managed encryption keys? | Add Cosmos DB / Blob customer-managed key config; Key Vault Premium for HSM |
| Multi-region required? | Add Cosmos DB geo-replication, Front Door multi-region origin group |
