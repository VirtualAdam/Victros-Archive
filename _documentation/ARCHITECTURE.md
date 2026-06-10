# Victros — Architecture

**Version:** 1.3.0 (SRS gap remediation)
**Last updated:** 2026-06-10

---

## System Overview

Victros is a **Strategic Reasoning Schema (SRS)** — a deterministic diagnosis engine for B2B sales deals with an LLM coaching interface. The LLM is the voice; the schema is the brain.

```
User Input (text / button / fields)
    → Intent Capture         (LLM: situation framing)
    → Situation Validation    (user confirms understanding)
    → Structured Inputs       (6 required fields collected)
    → Signal Extraction       (system-derived with confidence scores)
    → Signal Validation       (preconditions, confidence thresholds, evidence gates)
    → Quality Gate            (lever coverage check — critical gaps block evaluation)
    → Decision Engine         (deterministic: signals → patterns → strategy → actions)
    → Pattern Diagnostics     (user validates structural diagnosis)
    → Alignment Checkpoint    (Aligned / Doesn't match / Something changed / New session)
    → Strategy Presentation   (explanation: condition → risk → strategy → execution)
    → Action Selection        (user selects representative action)
    → Monitoring              (stay course / address next issue / exit / new session)
```

**Core separation:**

| Layer | Authority | Responsibility |
|-------|-----------|----------------|
| Decision Engine | System | Pattern activation, priority selection, strategy path — fully deterministic |
| LLM Services | System (voice) | Extraction, explanation, coaching narrative — constrained by schema |
| User | Human | Confirms inputs, validates diagnosis, selects actions, controls session |

No schema state is updated without explicit user confirmation. Strategy selection is fully deterministic and auditable regardless of LLM model.

---

## Data Flow (Engine Pipeline)

The decision engine runs inside the EVALUATING state. All steps are deterministic. No LLM.

```
E1 — Signal Activation
     Active signals advance lever states (WEAK → CONNECTED)

E2 — Signal-to-Pattern Mapping (signal-driven, OR logic)
     Each signal carries target_patterns; a pattern activates when
     any contributing signal targets it

E3 — PatternWeight Computation
     PatternWeight = max(SignalSeverity) + StructuralBonus(1.0)
                   + DensityFactor((n-1)*0.5) + LeverWeight(1.0)

E4 — Priority Pattern Selection (6-step tiebreaker)
     1. PatternWeight (highest wins)
     2. PatternSeverity (CRITICAL > HIGH > MEDIUM > LOW)
     3. Structural Precedence (structural > momentum)
     4. Lever Priority (case_for_change → champion → EB → decision_process
        → consensus → differentiation → urgency)
     5. Earliest Zone
     6. Stable sort (schema authoring error if reached)

E5 — Secondary Pattern Assignment
     All non-priority patterns; display limited to 1 secondary

E6 — StrategyPath Selection (multi-factor composite ranking)
     From priority pattern's candidate_strategy_path_keys only
     Filtered by: disqualifying conditions, entry conditions
     Ranked by: lever_alignment (0-5) + resolution_match (0-3) + entry_strength (0-N)
     ResolutionType = StrategyPath.mode (RECOVER | ADVANCE | EXIT)
```

### Decision Snapshots

Each evaluation run captures a `DecisionSnapshot` — an immutable record of engine state:
- `snapshot_id`, `session_id`, `evaluation_run_id` (increments per session)
- Active signals with confidence scores, lever states, patterns, strategy
- Signal quality warnings
- Enables cross-evaluation diffing for audit and re-evaluation tracking

---

## State Machine

```
S1  NEW_SESSION             → INTENT_CAPTURE
S2  INTENT_CAPTURE          → SITUATION_VALIDATION
S3  SITUATION_VALIDATION    → INTAKE | INTENT_CAPTURE (correction)
S4  INTAKE                  → AWAITING_CONFIRMATION
S5  AWAITING_CONFIRMATION   → EVALUATING | INTAKE (adjust/reject)
S6  EVALUATING              → PATTERN_DIAGNOSTICS | INTAKE (no signals)
S7  PATTERN_DIAGNOSTICS     → PRESENTING_DIAGNOSIS | INTAKE (reject)
S8  PRESENTING_DIAGNOSIS    → ALIGNMENT_CHECKPOINT
S9  ALIGNMENT_CHECKPOINT    → ACTION_SELECTION (aligned) | DUAL_PATTERN_TRADEOFF
                              | INTAKE (doesn't match / something changed) | ALIGNMENT_CHECKPOINT (stay)
S10 DUAL_PATTERN_TRADEOFF   → ACTION_SELECTION
S11 ACTION_SELECTION        → MONITORING
S12 MONITORING              → MONITORING | RE_EVALUATING | SESSION_PAUSED | SESSION_COMPLETE | ALIGNMENT_CHECKPOINT
S13 RE_EVALUATING           → PRESENTING_DIAGNOSIS | MONITORING | SESSION_COMPLETE
    SESSION_PAUSED          → MONITORING | INTENT_CAPTURE
    SESSION_COMPLETE        → INTENT_CAPTURE
```

Two-loop architecture:
- **Loop 1 (Evaluation):** INTENT_CAPTURE → ... → ALIGNMENT_CHECKPOINT → ACTION_SELECTION → MONITORING
- **Loop 2 (Re-evaluation):** MONITORING → RE_EVALUATING → PRESENTING_DIAGNOSIS → ALIGNMENT_CHECKPOINT → ACTION_SELECTION → MONITORING

Every state has boolean entry and exit guards defined in `inputs/data-flow-logic.md`.

---

## API Surface

### Session Lifecycle

| Endpoint | Method | States | Description |
|----------|--------|--------|-------------|
| `/api/session/create` | POST | → INTENT_CAPTURE | Create session, returns prompt |
| `/api/session/{id}` | GET | any | Fetch current session state |
| `/api/session/{id}/input` | POST | INTENT_CAPTURE, INTAKE, MONITORING | Submit text, fields, or signals |
| `/api/session/{id}/confirm` | POST | SITUATION_VALIDATION, AWAITING_CONFIRMATION | Confirm/adjust/reject |
| `/api/session/{id}/confirm-patterns` | POST | PATTERN_DIAGNOSTICS | Binary confirm/reject diagnosis |
| `/api/session/{id}/confirm-understanding` | POST | PRESENTING_DIAGNOSIS | Confirm understanding of strategy |
| `/api/session/{id}/alignment-checkpoint` | POST | ALIGNMENT_CHECKPOINT | Aligned / doesn't match / something changed / new session |
| `/api/session/{id}/select-action` | POST | ACTION_SELECTION | Select representative action |
| `/api/session/{id}/dual-pattern` | POST | DUAL_PATTERN_TRADEOFF | Choose focus/combine/sequence |
| `/api/session/{id}/progress` | POST | MONITORING | Submit progress update |
| `/api/session/{id}/monitoring-action` | POST | MONITORING | Stay course / address next issue / exit / new session |
| `/api/session/{id}/resume` | POST | SESSION_PAUSED | Resume paused session to MONITORING |
| `/api/session/{id}/resolve-reevaluation` | POST | RE_EVALUATING | Resolve exit/transition |
| `/api/session/{id}/intake-gaps` | GET | INTAKE | Show missing required fields |
| `/api/sessions` | GET | — | List sessions by user_id |

### Schema (read-only, cached)

| Endpoint | Returns |
|----------|---------|
| `/api/schema/signals` | 23 signals |
| `/api/schema/patterns` | 22 patterns |
| `/api/schema/strategy-paths` | 13 strategy paths |
| `/api/schema/levers` | 7 levers |
| `/api/schema/sales-zones` | 4 sales zones |
| `/api/schema/representative-actions` | 85 actions |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + version |
| `/api/version` | GET | `{version, iteration, sha}` |
| `/api/general-assist` | POST | Non-strategic LLM assistance |
| `/api/snapshot/generate` | POST | Generate Pipeline Risk Snapshot |
| `/api/snapshot/latest` | GET | Retrieve latest snapshot |

---

## Backend Modules

| Module | Role |
|--------|------|
| `main.py` | FastAPI app factory, all endpoint handlers |
| `decision_engine.py` | Deterministic pipeline (E1–E6), PatternWeight, priority selection |
| `state_machine.py` | Valid transition table, `validate_transition()` |
| `pattern_diagnostics.py` | Pattern group formatting, binary confirmation processing |
| `schema_store.py` | Schema JSON loader, cross-reference validation |
| `session_manager.py` | File-based session CRUD |
| `db/base.py` | `SessionRepository` abstract base class |
| `db/cosmos.py` | Cosmos DB session repository (production) |
| `intake_tracker.py` | Structured input field tracking, gap detection |
| `readiness_check.py` | 6 required fields + signals_confirmed gate |
| `progress_evaluator.py` | Monitoring progress evaluation, exit/transition detection |
| `confirmation_gate.py` | Signal proposal formatting |
| `models.py` | Pydantic models (SessionState, DecisionResult, schema entities) |
| `snapshot/service.py` | Pipeline Risk Snapshot generation |
| `snapshot/renderer.py` | Markdown rendering for snapshots |
| `snapshot/renderer_html.py` | HTML rendering for snapshots |
| `snapshot/store.py` | Snapshot persistence (file or Cosmos) |
| `version.py` | Version tracking (semver + iteration + SHA) |
| `auth.py` | SWA Easy Auth header parsing (X-MS-CLIENT-PRINCIPAL) |
| `config.py` | Environment variable loading |

### LLM Services

| Module | Input | Output | Constraint |
|--------|-------|--------|------------|
| `llm/intent_router.py` | Free text | `{category, confidence}` | Must not activate schema state |
| `llm/extraction_service.py` | Free text + signal keys | `{candidate_signals, deal_attributes}` | Signals must be subset of known keys |
| `llm/explanation_service.py` | DecisionResult + context | Coaching narrative | No first-person opinion, observable verbs only |
| `llm/general_assist.py` | Free text | Coaching narrative | Must not activate signals or select strategy |
| `llm/client.py` | — | Azure AI Inference client | `VICTROS_FORCE_MOCK=true` for mock mode |

---

## Frontend

| Technology | Version |
|-----------|---------|
| React | 19 |
| TypeScript | 5.x |
| Vite | 8.x |
| Tailwind CSS | 4.x |
| TanStack Query | 5.x |

### Screen Components

| Screen | State(s) | Purpose |
|--------|----------|---------|
| `StartScreen` | — | Session create / resume |
| `IntentCaptureScreen` | INTENT_CAPTURE | Free-text deal description |
| `SituationValidationScreen` | SITUATION_VALIDATION | Confirm/correct situation summary |
| `IntakeScreen` | INTAKE | Structured field collection + signal selection |
| `ConfirmationScreen` | AWAITING_CONFIRMATION | Review proposed signals |
| `PatternDiagnosticsScreen` | PATTERN_DIAGNOSTICS | Binary confirm/reject diagnosis |
| `DiagnosisScreen` | PRESENTING_DIAGNOSIS, ACTION_SELECTION | Strategy explanation + action selection |
| `DualPatternScreen` | DUAL_PATTERN_TRADEOFF | Focus/Combine/Sequence |
| `MonitoringScreen` | MONITORING, RE_EVALUATING | Active strategy state |
| `SessionComplete` (inline) | SESSION_COMPLETE | Completion confirmation |

---

## Schema Entities

| Entity | Count | Source | Role |
|--------|-------|--------|------|
| Signals | 23 | `schema/signals.json` | Observable conditions; carry severity, type, lever impact, target_patterns |
| Patterns | 22 | `schema/patterns.json` | Structural diagnoses; activated by signals; carry candidate_strategy_path_keys |
| Strategy Paths | 13 | `schema/strategy_paths.json` | Resolution plans; entry/exit conditions; representative actions |
| Levers | 7 | `schema/levers.json` | Structural state variables (WEAK → CONNECTED → COMMITTED → EXECUTING) |
| Sales Zones | 4 | `schema/sales_zones.json` | Deal stage context (Discovery → Negotiation) |
| Representative Actions | 85 | `schema/representative_actions.json` | Executable seller behaviors per strategy path |
