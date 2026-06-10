# Victros POC — Architecture Design

## Overview

This document defines the technical architecture for the Victros Strategic Reasoning Schema (SRS) proof of concept. The POC validates one thesis: **given inputs, does the system consistently land on the correct StrategyPath?**

The architecture is intentionally minimal. No databases, no orchestration frameworks, no agent toolkits. The system is a deterministic decision engine with a conversational UI.

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Data Store | JSON files on disk | Simplest possible persistence; schema is static, session data is small |
| Backend | Python + FastAPI | Lightweight, async-capable, easy to prototype |
| Frontend | React | Card-centric UI with structured interactions |
| LLM | OpenAI API (GPT-4o or equivalent) | Extraction, explanation, coaching voice |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         React Frontend                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │
│  │ Card/Button  │  │  Chat Input   │  │  Deal Snapshot Display    │ │
│  │ Interaction  │  │  (Pivot Loop) │  │  (Signals, Patterns, etc) │ │
│  └──────┬──────┘  └──────┬───────┘  └────────────┬───────────────┘ │
└─────────┼────────────────┼───────────────────────┼─────────────────┘
          │                │                       │
          ▼                ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Server                                  │
│                                                                      │
│  ┌──────────────┐                                                    │
│  │ Intent Router │◄── Classifies input as Strategic vs General AI    │
│  └──────┬───────┘                                                    │
│         │                                                            │
│         ├──── Strategic ────┐          ┌─── General AI ───┐          │
│         ▼                   │          ▼                   │         │
│  ┌──────────────┐           │   ┌──────────────┐          │         │
│  │  Ingestion   │           │   │  LLM Service │          │         │
│  │  Layer       │           │   │  (Artifacts,  │          │         │
│  │              │           │   │   General Q&A)│          │         │
│  │ • Free text  │           │   └──────────────┘          │         │
│  │ • Attachments│           │                              │         │
│  │ • Button     │           │                              │         │
│  │   selections │           │                              │         │
│  └──────┬───────┘           │                              │         │
│         │                   │                              │         │
│         ▼                   │                              │         │
│  ┌──────────────┐           │                              │         │
│  │  Extraction  │           │                              │         │
│  │  Service     │           │                              │         │
│  │  (LLM)      │           │                              │         │
│  │              │           │                              │         │
│  │ Converts     │           │                              │         │
│  │ unstructured │           │                              │         │
│  │ input into   │           │                              │         │
│  │ candidate    │           │                              │         │
│  │ signals      │           │                              │         │
│  └──────┬───────┘           │                              │         │
│         │                   │                              │         │
│         ▼                   │                              │         │
│  ┌──────────────┐           │                              │         │
│  │  Confirmation│           │                              │         │
│  │  Gate        │◄──────────┘                              │         │
│  │              │   User must confirm                      │         │
│  │  Returns     │   before signal                          │         │
│  │  proposals   │   activation                             │         │
│  │  to UI       │                                          │         │
│  └──────┬───────┘                                          │         │
│         │ (user confirmed)                                 │         │
│         ▼                                                  │         │
│  ┌─────────────────────────────────────────┐               │         │
│  │         Decision Engine                  │               │         │
│  │         (Pure Python — No LLM)           │               │         │
│  │                                          │               │         │
│  │  ┌────────┐  ┌──────────┐  ┌──────────┐ │               │         │
│  │  │Signal  │→ │Pattern   │→ │Strategy  │ │               │         │
│  │  │Eval    │  │Activation│  │Path      │ │               │         │
│  │  │        │  │& Priority│  │Selection │ │               │         │
│  │  └────────┘  └──────────┘  └──────────┘ │               │         │
│  │                                          │               │         │
│  │  Reads: Schema JSON files                │               │         │
│  │  Reads/Writes: Session JSON files        │               │         │
│  └──────────────┬──────────────────────────┘               │         │
│                  │                                          │         │
│                  ▼                                          │         │
│  ┌──────────────────────────────────────────┐               │         │
│  │         Explanation Service               │               │         │
│  │         (LLM)                             │               │         │
│  │                                           │               │         │
│  │  Takes Decision Engine output:            │               │         │
│  │  • Primary Pattern                        │               │         │
│  │  • Secondary Patterns                     │               │         │
│  │  • StrategyPath                           │               │         │
│  │  • RepresentativeActions                  │               │         │
│  │                                           │               │         │
│  │  Produces:                                │               │         │
│  │  • Coaching-voice explanation             │               │         │
│  │  • Structural implication → Risk →        │◄──────────────┘         │
│  │    Recommendation (rendering order)       │                         │
│  │  • Natural language action descriptions   │                         │
│  └──────────────┬────────────────────────────┘                         │
│                  │                                                      │
│                  ▼                                                      │
│  ┌──────────────────────────────────────────┐                          │
│  │         Session Manager                   │                          │
│  │                                           │                          │
│  │  Reads/Writes: /sessions/{user}/{opp}.json│                          │
│  │                                           │                          │
│  │  Maintains per-session:                   │                          │
│  │  • Active Signals                         │                          │
│  │  • Active Patterns                        │                          │
│  │  • Selected StrategyPath                  │                          │
│  │  • Deal snapshot (stage, amount, date)    │                          │
│  │  • Interaction history                    │                          │
│  └───────────────────────────────────────────┘                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

File System (JSON)
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  /schema/                          /sessions/                           │
│  ├── sales_zones.json              ├── user_001/                        │
│  ├── signals.json                  │   ├── opp_acme_001.json            │
│  ├── patterns.json                 │   └── opp_globex_002.json          │
│  ├── strategy_paths.json           └── user_002/                        │
│  ├── levers.json                       └── opp_initech_001.json         │
│  └── representative_actions.json                                        │
│                                                                         │
│  /prompts/                                                              │
│  ├── intent_router.txt                                                  │
│  ├── extraction.txt                                                     │
│  ├── explanation.txt                                                    │
│  └── persona.txt                                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Schema Store (`/schema/` JSON files)

Static JSON files representing the founder's decision logic. Loaded into memory at server startup. Not modified at runtime.

**sales_zones.json** — The 4 normalized sales zones (e.g., Zone1: Early Stage - Discovery/Pre-Qualification). Each zone defines: purpose, core objectives, core strategies, strategy method, zone risk lever triggers, and qualification requirements.

**signals.json** — The 18 deal signals. Each signal defines: name, description, observable condition, polarity (positive/negative), severity, type (structural risk vs. momentum strength), affected levers, trigger input conditions, and target patterns.

**patterns.json** — The 20 structural patterns. Each pattern defines: name, summary, trigger signals, diagnostic questions, root cause themes, polarity, type, severity, resolution type (RECOVER/ADVANCE/EXIT), zone bias, affected levers, and candidate strategy path keys.

**strategy_paths.json** — The 12 strategy paths. Each defines: key, display name, description, mode (RECOVER/ADVANCE/EXIT), diagnostic question, activation polarity, target levers, dominant failure mode, zone bias, primary target pattern, entry conditions, disqualifying conditions, core objectives, core strategies, prohibited strategies, representative actions, champion/economic buyer required behavior, progress/negative signals, escalation triggers, and exit conditions (lever state + observable outcome). The `PositiveProgressSignals` and `NegativeProgressSignals` fields are used during MONITORING: when the user reports an action outcome (Yes/No/Partial), the system maps that outcome to candidate signals from these fields, which then flow through AWAITING_CONFIRMATION → RE_EVALUATING.

**levers.json** — The 7 cross-opportunity levers: Case for Change Strength, Champion Strength, Economic Buyer Commitment, Buyer Consensus, Decision Process Alignment, Differentiation Leverage, Buyer Urgency. Each defines: name, description, states (WEAK → CONNECTED → COMMITTED → EXECUTING).

**representative_actions.json** — Executable user behaviors tied to strategy paths. Each defines: action key, parent strategy path, description, and UX-verbatim text.

### 2. Decision Engine

Pure Python module. **No LLM calls.** This is the deterministic core.

**Inputs:** Set of confirmed active signals for a session.

**Processing steps:**
1. **Signal Evaluation** — Determine which signals are active based on confirmed user inputs. Each signal has a polarity (positive/negative) and affects specific levers.
2. **Pattern Activation** — For each pattern, check if its trigger signals are active. Compute pattern severity and structural scope.
3. **Pattern Collision Resolution** — When multiple patterns activate:
   - Structural risks take precedence over momentum patterns
   - Higher severity wins (CRITICAL > HIGH > MEDIUM > LOW)
   - Within same severity, prioritize by lever order (Case for Change → Champion → Economic Buyer → Consensus → Decision Process → Differentiation → Urgency)
   - Within same lever, earlier zone takes precedence
4. **Priority Pattern Selection** — EXIT patterns override all others. Otherwise, highest severity structural risk becomes the priority pattern. Secondary patterns are preserved for context.
5. **StrategyPath Selection** — From the priority pattern's `CandidateStrategyPathKeys`, filter by:
   - Entry conditions satisfied
   - Disqualifying conditions not present
   - Zone alignment
   - Select one primary path
6. **Action Surfacing** — Load RepresentativeActions for the selected StrategyPath.

**Re-evaluation:** The Decision Engine runs identically during re-evaluation (after monitoring feedback produces new confirmed signals). The same pipeline executes with the updated signal set. The output may confirm the current StrategyPath, select a different one, or activate an EXIT pattern — the engine is stateless and treats every run the same way.

**Output:** A `DecisionResult` object:
```python
@dataclass
class DecisionResult:
    primary_pattern: Pattern
    secondary_patterns: list[Pattern]
    strategy_path: StrategyPath
    representative_actions: list[Action]
    active_signals: list[Signal]
    lever_states: dict[str, str]  # lever_name → state
    zone: SalesZone
```

### 3. Intent Router

Classifies every user interaction into one of two categories:

| Category | Routing | LLM Authority |
|---|---|---|
| **Strategic Reasoning** | Schema-constrained pipeline | LLM explains only; cannot determine strategy |
| **General AI Assistance** | Direct LLM response | LLM responds freely (emails, brainstorming, etc.) |

For the POC, this can be a simple LLM prompt classification call with the two categories and examples. If the input includes signal-related language, pattern references, deal strategy, or schema elements, it routes to the strategic pipeline. Otherwise, general assistance.

### 4. Ingestion Layer + Extraction Service

Handles three input types:

| Input Type | Flow |
|---|---|
| **Button/Card selection** | Direct signal activation (no LLM needed) → Confirmation Gate |
| **Free text** (Pivot Loop) | LLM extraction → candidate signals → Confirmation Gate |
| **Attachments** (CRM export, notes, screenshots) | LLM extraction → candidate deal attributes + signals → Confirmation Gate |

The Extraction Service uses an LLM prompt constrained to only propose updates from the known signal set. It cannot invent signals outside `signals.json`.

### 5. Confirmation Gate

All proposed signal changes must pass through user confirmation before entering the Decision Engine. Renders a short confirmation card:
- Bullet summary (2-4 items)
- Options: "Yes, that's accurate" / "Adjust" / "Not correct"

No schema state is modified without explicit user confirmation.

After confirmation, the system runs a **Readiness Check** before routing to the Decision Engine. The check requires two conditions: (1) a deal stage is present (determines Sales Zone), and (2) at least one signal is confirmed. If either is missing, the session returns to INTAKE to ask for the specific gap. If both are met, the session transitions to EVALUATING.

### 6. Explanation Service

Takes the `DecisionResult` from the Decision Engine and produces natural language output. Governed by:

**Rendering Order:**
1. Structural implication first (what deal condition exists)
2. Risk explanation second (why it matters)
3. Recommended strategic focus third (what to do)
4. Pattern label optional and secondary

**Voice constraints:**
- Persona: calm, experienced sales manager (not assistant, not chatbot)
- Must reference schema elements explicitly ("Victros identified..." not "I think...")
- Must not present reasoning as its own independent judgment
- Observable verbs only (ask, map, align, validate, confirm, request)

**Prompt template** loaded from `/prompts/explanation.txt` — includes persona definition, rendering order rules, and schema context injection.

### 7. Session Manager

Manages per-user, per-opportunity state as JSON files on disk.

**Session file structure** (`/sessions/{user_id}/{opportunity_id}.json`):
```json
{
  "session_id": "uuid",
  "user_id": "user_001",
  "opportunity_id": "opp_acme_001",
  "created_at": "2026-03-30T10:00:00Z",
  "updated_at": "2026-03-30T14:30:00Z",
  "deal_snapshot": {
    "stage": "3_Validation",
    "close_date": "2026-06-30",
    "amount": 1200000,
    "notes": "Compliance-led initiative, security not yet aligned"
  },
  "intake_readiness": {
    "deal_stage": "present",
    "deal_close_date": "present",
    "deal_amount": "present",
    "deal_notes": "present",
    "signals_confirmed": true
  },
  "active_signals": ["single_threaded_contact", "competition_gaining_mindshare", "validation_process_misalignment"],
  "active_patterns": {
    "primary": "single_threaded_risk",
    "secondary": ["competitive_mindshare", "process_misalignment"]
  },
  "selected_strategy_path": "selling_to_consensus",
  "lever_states": {
    "case_for_change_strength": "CONNECTED",
    "champion_strength": "CONNECTED",
    "economic_buyer_commitment": "WEAK",
    "buyer_consensus": "WEAK",
    "decision_process_alignment": "WEAK",
    "differentiation_leverage": "WEAK",
    "buyer_urgency": "CONNECTED"
  },
  "interaction_history": [
    {
      "timestamp": "2026-03-30T10:00:00Z",
      "type": "user_input",
      "content": "I have a compliance director who really likes Cyera..."
    },
    {
      "timestamp": "2026-03-30T10:00:05Z",
      "type": "system_response",
      "content": "Here's how I'm understanding the situation...",
      "signals_proposed": ["single_threaded_contact", "competition_gaining_mindshare"],
      "user_confirmed": true
    }
  ]
}
```

### 8. React Frontend

Card-centric, button-first interface following the POC spec's UX rules.

**Core interaction pattern per screen:**
1. Context/teaching line (1 sentence)
2. Agent question (1 focused decision)
3. Structured response options (2-4 buttons/cards)
4. Clear CTA (one next step)

**Key UI states:**
- Deal intake (snapshot entry / attachment upload)
- Signal confirmation cards
- Pattern diagnosis display
- StrategyPath recommendation with explanation
- RepresentativeAction selection
- Pivot Loop (free text → confirmation → back to cards)
- Dual Pattern tradeoff (Focus / Combine / Sequence options)

---

## API Endpoints (FastAPI)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/session/create` | Create new opportunity session |
| GET | `/api/session/{session_id}` | Get current session state |
| POST | `/api/session/{session_id}/input` | Submit user input (button, text, or attachment) |
| POST | `/api/session/{session_id}/confirm` | Confirm or reject proposed signal changes |
| POST | `/api/session/{session_id}/select-action` | Select a representative action |
| POST | `/api/session/{session_id}/dual-pattern` | Handle dual pattern choice (Focus/Combine/Sequence) |
| POST | `/api/general-assist` | General AI assistance (not schema-constrained) |
| GET | `/api/schema/signals` | List all available signals (for debug/admin) |
| GET | `/api/schema/patterns` | List all patterns (for debug/admin) |
| GET | `/api/schema/strategy-paths` | List all strategy paths (for debug/admin) |

---

## LLM Usage Boundaries

| Component | LLM Used? | Purpose | Authority |
|---|---|---|---|
| Intent Router | Yes | Classify input type | Routing only |
| Extraction Service | Yes | Convert free text / attachments to candidate signals | Proposes only; cannot activate |
| Decision Engine | **No** | Signal → Pattern → StrategyPath evaluation | **Sole strategic authority** |
| Explanation Service | Yes | Translate DecisionResult into coaching narrative | Voice only; cannot alter strategy |
| General AI Assist | Yes | Artifacts, drafting, brainstorming | Free (but cannot modify schema state) |

---

## Prompt Templates (`/prompts/`)

| File | Used By | Purpose |
|---|---|---|
| `intent_router.txt` | Intent Router | Classify user input as Strategic vs General AI |
| `extraction.txt` | Extraction Service | Extract candidate signals from free text. Constrained to known signal keys from schema |
| `explanation.txt` | Explanation Service | Generate coaching-voice explanation from DecisionResult. Includes persona, rendering order, and schema trust rules |
| `persona.txt` | All LLM calls | Base persona definition: calm, experienced sales manager. Referenced by other prompts |

---

## Directory Structure (POC Codebase)

```
victros-poc/
├── server/
│   ├── main.py                    # FastAPI app, endpoint definitions
│   ├── decision_engine.py         # Pure deterministic logic (no LLM)
│   ├── intent_router.py           # Input classification
│   ├── extraction_service.py      # LLM-based signal extraction
│   ├── explanation_service.py     # LLM-based coaching narrative
│   ├── session_manager.py         # Session CRUD, JSON file I/O
│   ├── llm_client.py              # OpenAI API wrapper
│   ├── models.py                  # Pydantic models for all data types
│   └── config.py                  # API keys, file paths, settings
├── schema/
│   ├── sales_zones.json
│   ├── signals.json
│   ├── patterns.json
│   ├── strategy_paths.json
│   ├── levers.json
│   └── representative_actions.json
├── prompts/
│   ├── intent_router.txt
│   ├── extraction.txt
│   ├── explanation.txt
│   └── persona.txt
├── sessions/                      # Runtime session data (gitignored)
├── client/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── CardSelector.tsx    # Button/card interaction component
│   │   │   ├── ChatInput.tsx       # Free text input (pivot loop)
│   │   │   ├── ConfirmationCard.tsx # Signal confirmation UI
│   │   │   ├── DealSnapshot.tsx    # Deal info display
│   │   │   ├── DiagnosisView.tsx   # Pattern/signal diagnosis
│   │   │   ├── StrategyView.tsx    # StrategyPath recommendation
│   │   │   └── ActionSelector.tsx  # RepresentativeAction picker
│   │   ├── hooks/
│   │   │   └── useSession.ts       # Session state management
│   │   └── api/
│   │       └── client.ts           # FastAPI client
│   └── package.json
├── tests/
│   ├── test_decision_engine.py     # Core validation: inputs → correct StrategyPath
│   ├── test_pattern_collision.py   # Pattern priority resolution tests
│   └── test_signal_activation.py   # Signal evaluation tests
└── README.md
```

---

## Testing / Validation Strategy

The POC success criterion: **"The system consistently outputs the correct StrategyPath."**

**Test approach:**
1. Define scenario fixtures: each fixture specifies a set of active signals and the expected priority pattern + strategy path
2. Run each fixture through the Decision Engine
3. Assert the output matches expected results
4. Cover edge cases: pattern collisions, same-severity ties, EXIT pattern overrides, disqualifying conditions

These tests validate the deterministic core independent of any LLM behavior.

---

## What Is NOT In Scope

- Authentication (simple hardcoded user IDs for POC)
- Deployment / hosting infrastructure
- CRM integrations
- Multi-user collaboration
- Revenue Graph / knowledge graph
- Authoring Studio
- Scenario Planner
- Performance analytics
- Agent frameworks or orchestration tools
