# Victros — Strategic Reasoning Schema (SRS)
## Engineering Specification

**Project:** Victros SRS — B2B Sales Strategy System  
**Author:** Wiedemann Labs  
**Prepared for:** Richard Rivera, Founder  
**Purpose:** Authoritative design and functional specification — describes the intended production architecture, component contracts, and system behavior

---

## 1. Purpose and Problem Statement

Enterprise AI has made significant progress automating operational and data-driven tasks. What remains largely unsolved is AI for strategic human reasoning — the complex, judgment-driven decisions made by experienced domain experts.

In B2B sales, these decisions include: diagnosing deal structure, identifying the correct strategic response, and executing the right actions at the right time. Today this expertise lives in people, not systems. The result is inconsistent execution, reliance on scarce senior talent, and decision quality that does not scale.

**Victros addresses this through the Strategic Reasoning Schema (SRS):** a structured reasoning layer that encodes expert strategic logic into a deterministic decision system, constrains AI to reason through defined paths, and delivers expert-level strategic guidance through a human coaching interface.

B2B sales is the proving ground — chosen because it is one of the most complex strategic domains while still being governed by deterministic structural logic. The goal is not a sales tool. It is proof that expert judgment can be codified, constrained, and delivered at scale through AI.

---

## 2. System Architecture

The SRS operates as a layered reasoning pipeline. The LLM does not participate in strategy selection — it serves as the extraction, explanation, and coaching interface over a deterministic engine.

```
User Input (text / button / attachment)
    → Intent Router            (LLM: strategic or general?)
    → Extraction Service       (LLM: signals + deal attributes from text)
    → Confirmation Gate        (user confirms proposed schema update)
    → Decision Engine          (deterministic: pattern → path → actions)
         ↓
    Explanation Service        (LLM: coaching narrative from DecisionResult)
    General Assist             (LLM: non-strategic requests in coaching voice)
```

**Core separation of responsibilities:**

| Layer | Responsibility |
|---|---|
| SRS Decision Engine | Sole authority for pattern activation and strategy selection |
| LLM Services | Extraction, explanation, routing, and general assistance |
| User | Final decision authority — confirms all schema state updates |

No schema state may be updated without explicit user confirmation. The LLM may propose; it never decides. Strategy selection is fully deterministic and auditable regardless of which LLM model is in use.

---

## 3. Schema Content

The schema is authored from the full SRS content and stored as structured JSON. All entities are cross-referenced and validated at load time. Malformed or inconsistent schema raises a typed error before the system starts — the application will not run against a broken schema.

| Schema Entity | Count | Role |
|---|---|---|
| Signals | 23 | Observable conditions; trigger patterns; advance lever states |
| Patterns | 22 | Structural diagnoses; severity-ranked; map to strategy paths |
| Strategy Paths | 13 | Targeted structural resolutions; zone and lever-aligned |
| Levers | 7 | Unifying structural logic across all reasoning layers |
| Sales Zones | 4 | Deal stage context (Discovery → Negotiation) |
| Representative Actions | 85 | Executable user behaviors per strategy path |

All schema entities are immutable at runtime. Schema is loaded once at application startup and shared across all requests.

---

## 4. Decision Engine

The Decision Engine is a stateless, deterministic Python service. Every call to `run()` is independent and produces a `DecisionResult` containing the full reasoning output. Given the same inputs it always produces the same output — no probabilistic components, no LLM involvement.

**Pipeline steps:**

1. **Signal Evaluation** — Active signals advance lever states from WEAK → CONNECTED
2. **Pattern Activation** — Patterns activate when all trigger signals are present
3. **Collision Resolution** — Deterministic priority selection across competing patterns:
   - EXIT patterns take highest priority (advisory — the system surfaces an exit recommendation; the user retains final authority)
   - Structural risk patterns outrank momentum patterns
   - Higher severity wins (CRITICAL > HIGH > MEDIUM > LOW)
   - Lever order tiebreak (Case for Change → Champion → Economic Buyer → Consensus → Decision Process → Differentiation → Urgency)
   - Zone order tiebreak
4. **Strategy Path Selection** — Filtered by zone alignment; entry and disqualifying conditions honored
5. **Action Surfacing** — Representative actions loaded for the selected strategy path

**Output — `DecisionResult`:**
- Primary pattern (key)
- Secondary patterns (keys)
- Selected strategy path (key)
- Representative actions (keys)
- Lever states (all 7, updated from signal evaluation)
- Sales zone

---

## 5. LLM Services

Four LLM service modules operate as the natural language interface over the deterministic engine. All services communicate with **Azure AI Inference** through a shared client factory, and all are model-agnostic — the deployed model is controlled entirely by environment configuration with no code changes required.

**Model configuration:**
```
VICTROS_AI_ENDPOINT    Azure AI Inference endpoint URL
VICTROS_AI_KEY         Azure AI Inference key
VICTROS_AI_DEPLOYMENT  Model deployment name (e.g. gpt-4o, Phi-4, Llama-3-70B)
```

Swapping models requires changing `VICTROS_AI_DEPLOYMENT` only. The four service modules do not reference the model name.

### Service Contracts

| Service | Input | Output | Constraint |
|---|---|---|---|
| **Intent Router** | Free text | `{category: "strategic"\|"general", confidence: float}` | Must not activate schema state |
| **Extraction Service** | Free text + known signal keys | `{candidate_signals: [...], deal_attributes: {...}}` | `candidate_signals` must be a strict subset of known signal keys |
| **Explanation Service** | `DecisionResult` + context | Coaching narrative string | No first-person opinion language; uses observable verbs only |
| **General Assist** | Free text | Coaching narrative string | Must not activate signals or select strategy paths |

**Extraction Service — Pivot variant:**  
`extract_pivot(text, known_keys)` → `{add_signals, remove_signals, update_deal, explanation}`  
Used for re-evaluation inputs; produces a schema delta rather than a full extraction.

**Explanation Service — Context modes:**
- `diagnosis` — primary pattern + strategy + representative actions
- `tradeoff` — dual-pattern resolution options (Focus / Combine / Sequence)
- `monitoring` — progress check against active strategy
- `summary` — full session narrative at close

### Observability

Every LLM service call emits one structured JSON log line to stdout containing:

| Field | Notes |
|---|---|
| `service` | `extraction`, `explanation`, `intent_router`, `general_assist` |
| `model` | Deployment name from configuration |
| `session_id` | Request correlation via Python `ContextVar` |
| `prompt_tokens` | From API usage response |
| `completion_tokens` | From API usage response |
| `latency_ms` | Wall time of the API call |
| `success` | Boolean |
| `error` | Exception class and message on failure only |

Azure Monitor / Application Insights ingests stdout JSON logs automatically in cloud deployment. Raw prompt and completion text are suppressed by default and enabled only via `LLM_DEV_LOGGING=true` for local development — these fields may contain PII and must never be enabled in production.

---

## 6. Session and API Layer

A FastAPI REST server provides the full session lifecycle, schema access, and executive reporting layer.

### Session State Machine

Sessions follow a defined state machine. Transitions are validated at each step.

```
NEW_SESSION → INTAKE → AWAITING_CONFIRMATION → PRESENTING_DIAGNOSIS
           ↘                                          ↓
             ←←←←←←←← (adjust / reject) ←←←←←  ACTION_SELECTION
                                                       ↓
                                              DUAL_PATTERN_TRADEOFF
                                                       ↓
                                                  MONITORING
                                                       ↓
                                              RE_EVALUATING (pivot)
```

### Session State Fields

Each session stores: `session_id`, `user_id`, `opportunity_id`, `state`, `deal_snapshot` (stage, amount, close date), `active_signals`, `active_patterns` (primary + secondary), `selected_strategy_path`, `lever_states` (all 7), `interaction_history`, `intake_readiness`, `created_at`, `updated_at`.

### API Surface

**Session lifecycle:**

| Endpoint | Method | Description |
|---|---|---|
| `/api/session/create` | POST | Create session for user + opportunity |
| `/api/session/{id}` | GET | Fetch current session state |
| `/api/session/{id}/input` | POST | Submit intake: `button` (signal keys), `text` (free text), or `attachment` |
| `/api/session/{id}/confirm` | POST | Confirm, adjust, or reject a signal proposal |
| `/api/session/{id}/select-action` | POST | Select a representative action; transitions to MONITORING |
| `/api/session/{id}/dual-pattern` | POST | Resolve dual-pattern tradeoff (focus / combine / sequence) |

**Schema (read-only, cached at client):**

| Endpoint | Returns |
|---|---|
| `/api/schema/signals` | All 23 signals |
| `/api/schema/patterns` | All 22 patterns |
| `/api/schema/strategy-paths` | All 13 strategy paths |
| `/api/schema/levers` | All 7 levers |
| `/api/schema/sales-zones` | All 4 sales zones |
| `/api/schema/representative-actions` | All 85 representative actions |

**Executive reporting:**

| Endpoint | Method | Description |
|---|---|---|
| `/api/snapshot/generate` | POST | Generate (or re-generate) the Pipeline Risk Snapshot for the current week |
| `/api/snapshot/latest` | GET | Retrieve the most recently generated snapshot document |

**General:**

| Endpoint | Method | Description |
|---|---|---|
| `/api/general-assist` | POST | Non-strategic LLM assistance in the Victros coaching voice |
| `/health` | GET | Service health check |

---

## 7. Data Persistence

Session and snapshot state is persisted in **Azure Cosmos DB** using the NoSQL API. The system uses a repository pattern — the storage backend is injected via configuration, and the application code is identical regardless of which backend is active.

### Configuration

```
STORAGE_BACKEND          "cosmos" (production) or "file" (local development without Docker)
COSMOS_CONNECTION_STRING  Azure Cosmos DB connection string
COSMOS_VERIFY_SSL        "false" for local emulator only
```

### Schema

**`sessions` container** — partition key: `/session_id`  
One document per session. Document shape mirrors the `SessionState` Pydantic model directly. All session fields are stored as-is; no relational joins required.

**`snapshots` container** — partition key: `/week_start`  
One document per calendar week. Stores aggregate metric totals only (not full session state) for week-over-week delta computation. Documents are upserted — generating a snapshot twice within a week overwrites the existing record.

### Local Development

The **Azure Cosmos DB Linux Emulator** (`mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator`) provides an identical wire protocol locally. The application uses the same `azure-cosmos` SDK and the same connection string format. There is no MongoDB compatibility layer — the emulator speaks the native Cosmos NoSQL protocol.

---

## 8. Executive Pipeline Risk Snapshot

The Pipeline Risk Snapshot is a weekly, fixed-format executive artifact generated from live session state. It provides CRO and Sales VP visibility into structural pipeline risk, intervention progress, and decision quality without requiring dashboard access or CRM interpretation.

The snapshot is not derived from CRM activity, engagement metrics, or statistical scoring. It is a system-generated view of structural truth extracted from live deal strategy sessions.

### Generation

Snapshots are generated on demand via `POST /api/snapshot/generate`. Generation is idempotent within a week — calling twice overwrites the stored document. Week boundaries are defined as Sunday 00:00 UTC through Saturday 23:59 UTC.

### Content Structure

**Section 1 — Executive Metric Blocks**

| Metric | Definition |
|---|---|
| Pipeline Value | Sum of `deal_snapshot.amount` across all diagnosed sessions |
| Active Deals | Count of sessions in a diagnosed state |
| Deals at Structural Risk | Sessions with ≥ 1 lever at WEAK |
| Structural Risks Resolved | Total non-WEAK lever states across all diagnosed sessions |
| Pipeline Value Strengthened | Sum of deal amounts for sessions with ≥ 1 lever advanced beyond WEAK |

All metrics include week-over-week delta (absolute change). Deltas are computed by comparing against the stored `PipelineSnapshotDocument` from the prior week. First-generation snapshots show N/A for all deltas.

**Section 2 — Active Structural Risk (Deal Table)**  
One entry per session with ≥ 1 WEAK lever, sorted by deal value descending. Each entry shows: opportunity ID, owner, zone, core structural risks (lever names at WEAK — primary risk bolded), active strategy path, and next recommended move (sourced from the `ux_text` of the last selected representative action in session history).

**Section 3 — Forecast Threats**  
Three aggregate breakdowns across all diagnosed sessions:
- **Top Failure Modes** — % of sessions where each lever is at WEAK
- **Active Strategy Interventions** — % distribution of selected strategy paths
- **Dominant Risk Patterns** — % of sessions exhibiting each primary pattern

### Output Format

Snapshots are rendered as Markdown. The Markdown output is returned directly from `POST /api/snapshot/generate` and is suitable for export or downstream formatting. PDF rendering is handled as a separate generation step outside the core API.

---

## 9. Frontend

The user-facing interface is a single-page React TypeScript application.

**Technology:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query  
**API communication:** Vite proxy (`/api` → backend); all schema queries cached with `staleTime: Infinity`

### Screen Flow

The frontend implements the session state machine as a screen router — each session state maps to exactly one screen.

| Session State | Screen | Description |
|---|---|---|
| No session | Start Screen | User ID + opportunity ID entry |
| `NEW_SESSION` / `INTAKE` | Intake Screen | Signal selection (buttons) or free-text input with demo scenario shortcuts |
| `AWAITING_CONFIRMATION` | Confirmation Screen | Review proposed signals; select deal zone (zone1–zone4) |
| `DUAL_PATTERN_TRADEOFF` | Dual Pattern Screen | Choose Focus / Combine / Sequence |
| `PRESENTING_DIAGNOSIS` / `ACTION_SELECTION` | Diagnosis Screen | Pattern, strategy path, action cards, lever health bars |
| `MONITORING` / `RE_EVALUATING` | Monitoring Screen | Active strategy, selected action, lever health, pivot entry |
| Pivot in progress | Pivot Screen | Free-text re-evaluation input |

### Schema Data

All six schema entity types are fetched at startup and held in TanStack Query's cache for the session lifetime. Components receive resolved schema objects (not raw keys), enabling real display names, lever tooltips (`why_it_matters`), and action `ux_text` on all screens.

---

## 10. Infrastructure and Deployment

### Local Development

All three services are orchestrated with Docker Compose:

```
cosmosdb    Azure Cosmos DB Linux Emulator — health-checked before backend starts
backend     FastAPI with hot-reload, source-mounted volume
frontend    Vite dev server, source-mounted volume
```

The Cosmos emulator uses its well-known public key (safe to commit). Backend health is gated on emulator readiness. The frontend proxy target (`VITE_BACKEND_URL`) resolves to `http://backend:8000` inside the network automatically.

### Cloud Deployment

Production infrastructure is provisioned via Azure Bicep. The deployment targets:
- **Azure Container Apps** — backend
- **Azure Static Web Apps** — frontend
- **Azure Cosmos DB** (NoSQL API) — session and snapshot storage
- **Azure AI Foundry** — LLM model deployments

Model configuration (`VICTROS_AI_ENDPOINT`, `VICTROS_AI_DEPLOYMENT`) is set as Container App environment variables in the Bicep template. Swapping LLM models in production requires a parameter change and redeployment — no application code changes.

---

## 11. Test Strategy

The system uses a three-tier test architecture. All tiers are independently runnable. Unit and integration tests are part of the standard CI pipeline. LLM accuracy evals require a live API key and are run separately.

| Tier | Scope | Count | Run condition |
|---|---|---|---|
| Unit | Deterministic: models, schema, engine, API, LLM contracts, snapshot service, LLM client/logger | 209 | Always (no external services) |
| Integration | Cosmos DB repository (IT-01 → IT-14) | 14 | Cosmos emulator running (`pytest -m integration`) |
| LLM Accuracy | Extraction and explanation eval suites against labeled fixtures | 50 examples | Live API key required (`pytest -m llm`) |

**Unit test coverage includes:**
- Pydantic model validation
- Schema load and cross-reference integrity
- All five Decision Engine pipeline steps including all collision resolution edge cases
- All API endpoints (session lifecycle, schema, snapshot, general assist)
- All four LLM service interface contracts and invariants (including the invariant that `candidate_signals` must be a strict subset of known schema keys)
- LLM client factory (mock mode detection, model deployment resolution, session context ContextVar)
- Structured logger output (field presence, dev mode gating, JSON validity)
- Snapshot service (metrics computation, WoW deltas, deal table construction, forecast threats)
- Snapshot renderer (section structure, currency formatting, delta annotations)
- Snapshot store round-trip (upsert, get by week, get latest)

**Integration test coverage (IT-01 → IT-14):**  
Full CRUD parity with the unit session manager tests, executed against the real Cosmos DB emulator: create, get, get non-existent, update all field types, append history, read-after-write consistency, `updated_at` advancement, and `list_sessions` user isolation.

---

## 12. System Invariants

The following properties hold unconditionally regardless of input, model, or configuration:

1. **LLM cannot alter strategy state.** All schema mutations require explicit user confirmation through the Confirmation Gate. The LLM proposes; the user decides.
2. **Signal keys are schema-bound.** The Extraction Service contract guarantees `candidate_signals` is a subset of known schema keys. No unknown signal can enter session state.
3. **Decision Engine is deterministic.** Identical inputs always produce identical outputs. No probabilistic components exist in the strategy selection pipeline.
4. **EXIT patterns are advisory.** The system surfaces EXIT recommendations but the user retains final authority. The engine cannot close or disqualify a deal.
5. **Schema is immutable at runtime.** Schema entities are loaded once at startup. No endpoint can modify schema content.
6. **Session state is confirmed, not inferred.** Lever states, patterns, and strategy paths are written only as the result of a completed `confirm` action, never as a side effect of input submission.
7. **Snapshot generation is idempotent within a week.** Calling `POST /api/snapshot/generate` twice in the same week overwrites, never duplicates.

---

## 13. Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Decision Engine | Pure Python — no external dependencies |
| Session / Snapshot Persistence | Azure Cosmos DB (NoSQL API); `azure-cosmos` SDK |
| LLM Interface | Azure AI Inference (`azure-ai-inference` SDK); model-agnostic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Infrastructure (local) | Docker Compose, Azure Cosmos DB Linux Emulator |
| Infrastructure (cloud) | Azure Container Apps, Azure Static Web Apps, Azure AI Foundry, Azure Bicep |
| Testing | pytest, pytest-asyncio, Vitest, jsdom |
| Schema Source | CSV → JSON (conversion script) |

---

*This document is the authoritative engineering specification for the Victros Strategic Reasoning Schema system. It describes the system as designed and intended for production. All architectural decisions, component contracts, system invariants, and behavioral specifications herein represent the target state of the system.*
