# Victros POC — Session State Machine & Data Flow

## Overview

Every user–opportunity session exists in exactly one state at any time. The state determines what the system is doing, what the UI shows, what the LLM is allowed to do, and which transitions are valid.

This document defines each state, its data flow, and the transitions between states.

---

## State Machine Diagram

```
                          ┌──────────────┐
                          │   NEW_SESSION │
                          └──────┬───────┘
                                 │ User creates session
                                 ▼
                          ┌──────────────┐
                     ┌───►│    INTAKE     │◄────────────────────┐
                     │    └──────┬───────┘                      │
                     │           │ User provides input           │
                     │           │ (text/attachment/buttons)     │
                     │           ▼                               │
                     │    ┌──────────────────────┐               │
                     │    │ AWAITING_CONFIRMATION │◄──────┐      │
                     │    └──────┬───────────────┘       │      │
                     │           │                        │      │
                     │     ┌─────┴─────┐                  │      │
                     │     │           │                  │      │
                     │  Confirmed   Rejected              │      │
                     │     │           │                  │      │
                     │     │           └──────────────────┼──────┘
                     │     ▼                              │
                     │    ┌──────────────┐                │
                     │    │  EVALUATING  │                │
                     │    └──────┬───────┘                │
                     │           │ Decision Engine runs    │
                     │           ▼                        │
                     │    ┌──────────────────────────┐    │
                     │    │ PRESENTING_DIAGNOSIS      │    │
                     │    │                           │    │
                     │    │ (if multiple patterns     │    │
                     │    │  above threshold)         │    │
                     │    └──────┬────────┬───────────┘    │
                     │           │        │                │
                     │     Single    Multiple              │
                     │     pattern   patterns              │
                     │           │        │                │
                     │           │        ▼                │
                     │           │  ┌─────────────────┐   │
                     │           │  │ DUAL_PATTERN_    │   │
                     │           │  │ TRADEOFF         │   │
                     │           │  └────────┬────────┘   │
                     │           │           │ User picks  │
                     │           │           │ Focus/      │
                     │           │           │ Combine/    │
                     │           │           │ Sequence    │
                     │           │           │             │
                     │           ▼           ▼             │
                     │    ┌──────────────────────┐        │
                     │    │  ACTION_SELECTION     │        │
                     │    └──────┬───────────────┘        │
                     │           │ User picks action       │
                     │           ▼                         │
                     │    ┌──────────────┐                 │
                     │    │  MONITORING   │                 │
                     │    └──┬───┬───┬───┘                 │
                     │       │   │   │                     │
                     │    Yes│ No│ Partial                  │
                     │       │   │   │                     │
                     │       │   │   └──► RE_EVALUATING ──►│
                     │       │   └──────► RE_EVALUATING ──►│
                     │       └──────────► RE_EVALUATING ──►│
                     │                          │          │
                     │                          └──────────┘
                     │
                     │    ┌──────────────┐
                     └────┤    PIVOT      │
                          └──────┬───────┘
                                 │ Extracted deltas
                                 ▼
                          Routes to AWAITING_CONFIRMATION
                          (shown above)

  Any state with user input ──► free text detected ──► PIVOT
```

---

## State Definitions

---

### 1. NEW_SESSION

**Purpose:** Initialize a fresh opportunity session for a user.

**Entry Condition:** User requests to start a new deal session.

**Data Created:**
```json
{
  "session_id": "generated_uuid",
  "user_id": "from_auth",
  "opportunity_id": "user_provided_or_generated",
  "created_at": "timestamp",
  "state": "NEW_SESSION",
  "deal_snapshot": null,
  "active_signals": [],
  "active_patterns": { "primary": null, "secondary": [] },
  "selected_strategy_path": null,
  "lever_states": {
    "case_for_change_strength": "WEAK",
    "champion_strength": "WEAK",
    "economic_buyer_commitment": "WEAK",
    "buyer_consensus": "WEAK",
    "decision_process_alignment": "WEAK",
    "differentiation_leverage": "WEAK",
    "buyer_urgency": "WEAK"
  },
  "interaction_history": []
}
```

The `intake_readiness` tracker is also initialized:
```json
{
  "intake_readiness": {
    "deal_stage": "missing",
    "deal_close_date": "missing",
    "deal_amount": "missing",
    "deal_notes": "missing",
    "signals_confirmed": false
  }
}
```

**UI Renders:** Welcome screen with persona greeting. "How can I help you win today?"

**Active Components:** Session Manager (creates file)

**LLM Authority:** Greeting only. No strategic reasoning.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| User provides any input (text, attachment, button) | INTAKE |

---

### 2. INTAKE

**Purpose:** Gather the information the Decision Engine needs to run. INTAKE is not a linear checklist — it is a **requirement-satisfaction loop** where the system tracks what it has, determines what's missing, and asks for the gaps. Inputs can arrive from any source, in any order, and a single source may satisfy multiple requirements at once.

**Entry Condition:** User submits deal context — could be free text describing the situation, an attachment (CRM export, notes, screenshot), or structured button responses to system questions.

#### Intake Requirements

The Decision Engine needs two categories of input to run:

| Category | Required Fields | Minimum to Proceed |
|---|---|---|
| **Deal Context** | Stage, Close Date, Amount, Notes | Stage (determines Sales Zone) |
| **Signals** | Any of the 18 schema-defined signals | At least 1 confirmed signal |

The system tracks a **readiness state** for the session:

```json
{
  "intake_readiness": {
    "deal_stage": "present",        // ← required
    "deal_close_date": "present",   // ← helpful but not blocking
    "deal_amount": "present",       // ← helpful but not blocking
    "deal_notes": "missing",        // ← optional
    "signals_confirmed": true       // ← required (at least 1)
  }
}
```

#### Source-Agnostic Filling

Any input source can satisfy any combination of requirements:

| Source | What it might provide | Example |
|---|---|---|
| CRM screenshot | All deal context + some signals | Stage=3_Validation, Amount=$1.2M, Close=June 30. System may also detect signal candidates from notes field. |
| Deal deck PDF | Partial deal context | Amount and stakeholder list, but no stage or close date |
| Free text narrative | Signals + partial deal context | "Compliance director moving fast, security not involved" → candidate signals + stakeholder info |
| Button selection | Signals directly | User taps "Single-Threaded Contact" and "Competition Gaining Mindshare" |
| System questions | One field at a time | "What buying stage would you place this deal today?" → Stage |

A single attachment could satisfy everything. Or the user might need 4 rounds of questions. The system doesn't care about the order — it cares about readiness.

#### Gap Detection

After each round of confirmed input, the system checks readiness:

```
After each confirmation cycle:
       │
       ▼
┌──────────────────────────────┐
│  Readiness Check              │
│                               │
│  Has deal stage?         ✓/✗  │
│  Has ≥1 confirmed signal? ✓/✗ │
└──────┬────────────┬──────────┘
       │            │
    Ready        Not ready
       │            │
       ▼            ▼
  EVALUATING     Ask for the
                 missing piece
                 (stays in INTAKE)
```

When the session is **not ready**, the system asks for the specific missing requirement — not a generic data dump request. The ask is focused:
- Missing stage: "What buying stage would you place this deal today?" (button selection)
- Missing signals: "I need to understand the structural risks. Tap the ones that are true right now." (signal cards)

When the session **is ready**, the system transitions to EVALUATING.

#### What Happens When Almost Everything Is Present But Something Is Missing

The system can proceed **as soon as the minimum is met** (stage + at least 1 signal). Missing optional fields (close date, amount, notes) don't block the engine — they reduce the quality of the LLM explanation layer's context, but the deterministic core runs on signals and zone alone.

If the **stage is missing**, the system cannot determine the Sales Zone, and the Decision Engine cannot run. The system must ask for it. This is a hard gate — not a deterministic "rejection," but a simple: "I need one more thing before I can diagnose this deal."

If **no signals are confirmed**, the engine has nothing to evaluate. The system must collect at least one signal through any source. Again, not a rejection — just: "Let me understand what you're seeing in this deal."

The system never refuses to proceed or tells the user the deal is invalid. It asks for the specific missing input in the coaching voice: calm, direct, one question at a time.

#### Data Flow (per input round)

```
User Input (text / attachment / button selection)
       │
       ▼
┌─────────────────┐
│  Intent Router   │ ◄── LLM classifies: Strategic or General AI?
└────┬────────┬───┘
     │        │
 Strategic  General AI
     │        │
     ▼        ▼
 Ingestion   LLM responds freely
 Layer       (no state change, stays
     │        in current state)
     ▼
┌─────────────────┐
│  Input Type?     │
└─┬──────┬─────┬──┘
  │      │     │
Button  Text  Attachment
  │      │     │
  │      ▼     ▼
  │   ┌─────────────────┐
  │   │ Extraction Svc   │ ◄── LLM extracts candidate signals
  │   │ (LLM)            │     + deal attributes from free text
  │   │                  │     or attachment. Constrained to
  │   │                  │     known signal keys and deal fields.
  │   └────────┬─────────┘
  │            │
  │            ▼
  │   Candidate signals + deal attributes
  │            │
  ▼            ▼
Direct    Proposed
signal    signal set
set            │
  │            │
  └─────┬──────┘
        ▼
  Transition to AWAITING_CONFIRMATION
        │
  (after confirmation, Readiness Check
   determines: EVALUATING or ask next gap)
```

**What gets extracted (examples):**
- From "I have a compliance director who likes Cyera and wants to move fast into a POC. Security and data teams aren't really involved yet."
  - Candidate signals: `single_threaded_contact`, `validation_process_misalignment`
  - Deal attributes: stakeholder = "Compliance Director", competitor = "Varonis"
  - Readiness: stage still missing, signals present → system asks for stage next
- From a CRM screenshot:
  - Deal attributes: stage, close date, amount, notes
  - Possibly candidate signals from notes field
  - Readiness: stage present, but signals may still need confirmation → system presents signal cards
- From button selections (e.g., user taps "Single-Threaded Contact" and "Competition Gaining Mindshare"):
  - Direct signals: `single_threaded_contact`, `competition_gaining_mindshare`
  - Readiness: if stage already present → ready → EVALUATING

**UI Renders:** Depends on what's needed next:
- Missing deal context: "What buying stage would you place this deal today?" (buttons)
- Missing signals: "Just tap the ones that are true right now." (signal cards)
- Offering input options: "Type in the chat or attach something — I'll extract the details." (chat + upload)

**Active Components:** Intent Router, Ingestion Layer, Extraction Service (if text/attachment), Readiness Check

**LLM Authority:** Extraction and classification only. Cannot activate signals or determine strategy.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| Signals/attributes extracted or selected | AWAITING_CONFIRMATION |
| Input classified as General AI | Stays in INTAKE (LLM responds, no state change) |

---

### 3. AWAITING_CONFIRMATION

**Purpose:** Present proposed signal changes to the user and wait for explicit confirmation before modifying schema state. This is the **gate** that preserves deterministic integrity.

**Entry Condition:** Extraction Service or button selection has produced a set of proposed signal activations or deal attribute changes.

**Data Flow:**
```
Proposed changes (from Extraction Service or buttons)
       │
       ▼
┌──────────────────────────┐
│  Confirmation Gate        │
│                           │
│  Formats proposals as:    │
│  • Bullet summary (2-4)   │
│  • Confirmation options    │
└────────────┬──────────────┘
             │
             ▼
  UI renders confirmation card
             │
       ┌─────┼──────┐
       │     │      │
      Yes  Adjust  Reject
       │     │      │
       │     │      └──► INTAKE (user restates)
       │     │
       │     └──► INTAKE (adjusted input re-extracted)
       │
       ▼
  Signals / deal attributes written to session state
  Lever states updated
       │
       ▼
┌──────────────────────────┐
│  Readiness Check          │
│                           │
│  Has deal stage?     ✓/✗  │
│  Has ≥1 signal?      ✓/✗  │
└──────┬────────────┬──────┘
       │            │
    Ready        Not ready
       │            │
       ▼            ▼
  EVALUATING     INTAKE
                 (ask for the
                  specific gap)
```

**Session Data Modified (on confirmation only):**
- `active_signals` — updated with confirmed signal keys
- `lever_states` — recalculated based on active signals
- `deal_snapshot` — updated with confirmed deal attributes
- `intake_readiness` — fields marked as present/missing
- `interaction_history` — confirmation event appended

**UI Renders:** Confirmation card:
```
Here's what I'm seeing:
• Single-threaded contact risk
• Competition gaining mindshare
• Validation process misalignment

Does this reflect the situation?

[Yes, that's accurate]  [Adjust]  [Not correct]
```

**Active Components:** Confirmation Gate, Readiness Check, Session Manager (writes on confirm)

**LLM Authority:** None. This is a pure UI interaction. No LLM calls.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| User confirms, readiness met (stage + ≥1 signal) | EVALUATING |
| User confirms, readiness NOT met | INTAKE (system asks for specific gap) |
| User wants to adjust | INTAKE (re-entry with adjusted context) |
| User rejects | INTAKE (re-entry, user restates) |
| User enters free text instead of tapping a button | PIVOT |

---

### 4. EVALUATING

**Purpose:** Run the deterministic Decision Engine. This is the core of the system — pure logic, no LLM, no ambiguity.

**Entry Condition:** User has confirmed signal activations. Session has an updated set of active signals.

**Data Flow:**
```
Session state (active_signals, lever_states)
       │
       ▼
┌────────────────────────────────────────────────┐
│              Decision Engine                    │
│              (Pure Python — No LLM)             │
│                                                 │
│  Step 1: Signal Evaluation                      │
│  ─ Load active signals from session             │
│  ─ Determine affected levers per signal         │
│  ─ Update lever states                          │
│                                                 │
│  Step 2: Pattern Activation                     │
│  ─ For each pattern in schema:                  │
│    ─ Check if trigger signals are active        │
│    ─ If yes: pattern is activated               │
│    ─ Compute severity, structural scope         │
│                                                 │
│  Step 3: Pattern Collision Resolution            │
│  ─ Structural > Momentum                        │
│  ─ Higher severity wins                         │
│  ─ Same severity: prioritize by lever order     │
│  ─ Same lever: earlier zone wins                │
│                                                 │
│  Step 4: Priority Pattern Selection              │
│  ─ EXIT patterns override all                   │
│  ─ Otherwise: highest severity structural risk  │
│  ─ Secondary patterns preserved                 │
│                                                 │
│  Step 5: StrategyPath Selection                  │
│  ─ Read priority pattern's                      │
│    CandidateStrategyPathKeys                    │
│  ─ Filter by EntryConditions (satisfied?)       │
│  ─ Filter by DisqualifyingConditions (absent?)  │
│  ─ Filter by zone alignment                     │
│  ─ Select one primary path                      │
│                                                 │
│  Step 6: Action Surfacing                        │
│  ─ Load RepresentativeActions for selected path │
│                                                 │
└──────────────────┬─────────────────────────────┘
                   │
                   ▼
            DecisionResult:
            {
              primary_pattern,
              secondary_patterns[],
              strategy_path,
              representative_actions[],
              active_signals[],
              lever_states{},
              zone
            }
                   │
                   ▼
  Session state updated:
  ─ active_patterns.primary
  ─ active_patterns.secondary
  ─ selected_strategy_path
  ─ lever_states
                   │
                   ▼
  Transition to PRESENTING_DIAGNOSIS
```

**Session Data Modified:**
- `active_patterns` — primary and secondary patterns set
- `selected_strategy_path` — set to selected path key
- `lever_states` — finalized

**UI Renders:** Loading/thinking indicator. No user interaction in this state.

**Active Components:** Decision Engine, Session Manager

**LLM Authority:** None. Zero LLM involvement.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| DecisionResult produced | PRESENTING_DIAGNOSIS |

---

### 5. PRESENTING_DIAGNOSIS

**Purpose:** Translate the DecisionResult into a coaching-voice explanation and present the strategy recommendation to the user.

**Entry Condition:** Decision Engine has produced a DecisionResult.

**Data Flow:**
```
DecisionResult (from Decision Engine)
       │
       ▼
┌──────────────────────────────────────┐
│  Explanation Service (LLM)           │
│                                       │
│  Input:                               │
│  ─ Primary Pattern (name, summary,    │
│    root cause themes)                 │
│  ─ Secondary Patterns                 │
│  ─ StrategyPath (display name,        │
│    core objectives, description)      │
│  ─ Active signals                     │
│  ─ Lever states                       │
│  ─ Deal snapshot                      │
│                                       │
│  Prompt constraints:                  │
│  ─ Rendering order enforced:          │
│    1. Structural implication          │
│    2. Risk explanation                │
│    3. Recommended strategic focus     │
│    4. Pattern label (optional)        │
│  ─ Persona: calm sales manager        │
│  ─ Must say "Victros identified..."   │
│    not "I think..."                   │
│  ─ Observable verbs only              │
│                                       │
│  Output:                              │
│  ─ Natural language diagnosis         │
│  ─ Strategy recommendation narrative  │
│  ─ "Does that match what you're       │
│     experiencing?" confirmation       │
└──────────────┬───────────────────────┘
               │
               ▼
  UI renders diagnosis + confirmation
               │
         ┌─────┼──────┐
         │     │      │
       Yes  Mostly  Not really
         │     │      │
         │     │      └──► INTAKE (user restates with corrections)
         │     │
         │     └──► Minor adjustment, stay in PRESENTING_DIAGNOSIS
         │          (re-render with adjusted framing)
         │
         ▼
   Check: multiple patterns above threshold?
         │
    ┌────┴────┐
    │         │
   No        Yes
    │         │
    ▼         ▼
  ACTION_   DUAL_PATTERN_
  SELECTION TRADEOFF
```

**UI Renders:** Diagnosis narrative followed by confirmation:
```
Right now, three structural patterns are showing up:

• Single-Threaded Risk
  Only one stakeholder is engaged, limiting consensus formation.

• Competitive Mindshare
  Buyer language is leaning toward a competitor's approach.

• Process Misalignment
  Requested validation approach does not align to your strengths.

The good news is this is a very common situation—and there's
a clear strategy to fix it.

Does that match what you're experiencing?

[Yes, exactly]  [Mostly]  [Not really]
```

**Active Components:** Explanation Service, Session Manager

**LLM Authority:** Translation and coaching voice only. Cannot alter strategy selection. Must reference schema elements explicitly.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| User confirms, single dominant pattern | ACTION_SELECTION |
| User confirms, multiple patterns above threshold | DUAL_PATTERN_TRADEOFF |
| User disagrees ("Not really") | INTAKE |
| User enters free text | PIVOT |

---

### 6. DUAL_PATTERN_TRADEOFF

**Purpose:** When multiple structural patterns are active above the severity threshold, present the user with a choice of how to handle parallel risks.

**Entry Condition:** DecisionResult contains multiple patterns above severity threshold. User has confirmed the diagnosis.

**Data Flow:**
```
Primary Pattern + Secondary Pattern(s)
       │
       ▼
┌──────────────────────────────────────┐
│  Explanation Service (LLM)            │
│                                       │
│  Explains:                            │
│  ─ "You're dealing with two           │
│     structural risks at the same      │
│     time."                            │
│  ─ Primary pattern and why it's       │
│     priority                          │
│  ─ Tradeoff options with              │
│     situational pros/cons             │
└──────────────┬───────────────────────┘
               │
               ▼
  UI renders tradeoff options (static set):
               │
       ┌───────┼───────┐
       │       │       │
     Focus  Combine  Sequence
       │       │       │
       └───────┼───────┘
               │
               ▼
  Session updated:
  ─ dual_pattern_approach: "focus" | "combine" | "sequence"
  ─ No change to primary StrategyPath
               │
               ▼
  Transition to ACTION_SELECTION
```

**Session Data Modified:**
- `dual_pattern_approach` — stores the user's choice
- The primary StrategyPath does NOT change. The approach only influences UX guidance framing.

**UI Renders:**
```
The priority to fix first is: [Primary Pattern → StrategyPath]

From here, you have three valid ways to proceed:

[Focus on priority]
Prioritize fixing this first before doing anything else.

[Combine both]
Use the current motion to also improve this gap.

[Sequence it]
Make progress on the current motion, then return to this.
```

**Active Components:** Explanation Service (for contextual pros/cons), Session Manager

**LLM Authority:** Explains tradeoffs in human terms. Cannot alter pattern priority or StrategyPath.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| User selects Focus, Combine, or Sequence | ACTION_SELECTION |
| User enters free text | PIVOT |

---

### 7. ACTION_SELECTION

**Purpose:** Present the RepresentativeActions for the active StrategyPath and let the user choose which move to execute next.

**Entry Condition:** StrategyPath is confirmed (directly from diagnosis or after dual-pattern tradeoff). User is ready to act.

**Data Flow:**
```
Active StrategyPath → RepresentativeActions
       │
       ▼
┌──────────────────────────────────────┐
│  Explanation Service (LLM)            │
│                                       │
│  Takes each RepresentativeAction and  │
│  renders it in natural language with  │
│  brief context.                       │
│                                       │
│  Cannot invent actions outside the    │
│  active StrategyPath.                 │
└──────────────┬───────────────────────┘
               │
               ▼
  UI renders action cards
               │
               ▼
  User selects one action
               │
               ▼
  Session updated:
  ─ selected_action: action_key
  ─ action_started_at: timestamp
               │
               ▼
  Transition to MONITORING
```

**UI Renders:**
```
Here are the strongest strategic moves from this position.
Select the move you want to focus on first.

[Run persona-specific outcome discussions]
Short conversations focused on each stakeholder's 
success criteria.

[Connect solution to stakeholder priorities]
Show how your approach solves what matters most 
to each persona.

[Use targeted proof for each stakeholder]
Customer stories, workshops, or demos tailored 
to each role.

[Sequence stakeholder conversations]
Plan the order of engagement to build aligned 
decision criteria.
```

**Active Components:** Explanation Service, Session Manager

**LLM Authority:** Explains actions in human terms. Cannot invent actions outside schema. Cannot prioritize actions (POC limitation).

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| User selects an action | MONITORING |
| User enters free text | PIVOT |

---

### 8. MONITORING

**Purpose:** Track whether the user executed the chosen action and what the outcome was. This is where the system waits for real-world feedback.

**Entry Condition:** User has selected a RepresentativeAction to execute.

**Data Flow:**
```
Selected action context
       │
       ▼
┌──────────────────────────────────────┐
│  Explanation Service (LLM)            │
│                                       │
│  Frames the monitoring question:      │
│  ─ What to watch for                  │
│  ─ What the outcome tells us          │
│  ─ Options: Yes / No / Partially      │
└──────────────┬───────────────────────┘
               │
               ▼
  UI renders progress check
               │
       ┌───────┼────────┐
       │       │        │
      Yes    No     Partially
  (positive) (negative) (mixed)
       │       │        │
       └───────┼────────┘
               │
               ▼
  Map outcome to signal updates:
  ─ Yes → activate PositiveProgressSignals
         (from StrategyPath schema)
  ─ No  → activate NegativeProgressSignals
  ─ Partially → context-dependent
               │
               ▼
  New signals proposed
               │
               ▼
  Transition to AWAITING_CONFIRMATION
  (then EVALUATING → system may stay 
   on same path or reclassify)
```

**Session Data Modified:**
- `action_outcome` — recorded on the selected action
- New candidate signals generated from the outcome

**UI Renders:**
```
Now we watch what happens next. This is the moment 
where a Champion becomes real.

Did your Champion complete the action we asked for?

[Yes — they completed it]
[No — they didn't follow through]
[Partially — they tried, but it didn't happen]
```

**Active Components:** Explanation Service, Ingestion Layer (maps outcome to signals), Session Manager

**LLM Authority:** Frames the question. Cannot determine what the outcome means strategically — that's the Decision Engine's job after re-evaluation.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| User reports outcome (Yes/No/Partial) | AWAITING_CONFIRMATION (with new proposed signals) |
| User enters free text | PIVOT |

---

### 9. RE_EVALUATING

**Purpose:** Re-run the Decision Engine after new signals have been confirmed. The system may stay on the current StrategyPath, switch to a different one, or escalate.

**Entry Condition:** User has confirmed new signal activations that resulted from monitoring feedback, a pivot loop, or escalation.

**Data Flow:**
```
Identical to EVALUATING, but with an updated signal set.

The Decision Engine runs the full pipeline:
─ Signal Evaluation (new + existing signals)
─ Pattern Activation
─ Pattern Collision Resolution
─ Priority Pattern Selection
─ StrategyPath Selection

Possible outcomes:
┌─────────────────────────────────────────────┐
│                                              │
│  1. Same StrategyPath, same pattern          │
│     → Continue to ACTION_SELECTION           │
│       (next action or same monitoring)       │
│                                              │
│  2. Same pattern, but exit conditions met    │
│     → Pattern resolved. Check for remaining  │
│       patterns → new PRESENTING_DIAGNOSIS    │
│       or session complete                    │
│                                              │
│  3. Different priority pattern emerged       │
│     → New StrategyPath selected              │
│     → PRESENTING_DIAGNOSIS (new strategy)    │
│                                              │
│  4. EXIT pattern activated                   │
│     → Advisory exit recommendation           │
│     → PRESENTING_DIAGNOSIS (exit advisory)   │
│                                              │
└─────────────────────────────────────────────┘
```

**Session Data Modified:** Same as EVALUATING — patterns, strategy path, lever states all recalculated.

**UI Renders:** Transition screen if strategy changed. Otherwise transparent to user.

**Active Components:** Decision Engine, Session Manager

**LLM Authority:** None during evaluation. Explanation Service activated in the subsequent state.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| Same strategy continues | ACTION_SELECTION |
| Exit conditions met, more patterns remain | PRESENTING_DIAGNOSIS |
| New priority pattern / strategy change | PRESENTING_DIAGNOSIS |
| All patterns resolved, deal structurally sound | SESSION_COMPLETE |

---

### 10. PIVOT

**Purpose:** Handle free-text input that deviates from the current structured flow. The user wants to express something outside the card/button options. The system must translate this back into structured schema elements without breaking deterministic reasoning.

**Entry Condition:** User enters free text at any point where the system expected a structured response (button/card tap).

**Data Flow:**
```
Free text input from user
       │
       ▼
┌──────────────────────────────────────┐
│  Extraction Service (LLM)             │
│                                       │
│  Interprets text and produces:        │
│  ─ Candidate signal additions         │
│  ─ Candidate signal removals          │
│  ─ Deal attribute changes             │
│  ─ Stakeholder role updates           │
│                                       │
│  Constrained to known schema keys.    │
│  Cannot invent new signals.           │
│                                       │
│  Output: Schema Delta                 │
│  {                                    │
│    "add_signals": [...],              │
│    "remove_signals": [...],           │
│    "update_deal": {...},              │
│    "explanation": "..."               │
│  }                                    │
└──────────────┬───────────────────────┘
               │
               ▼
  Transition to AWAITING_CONFIRMATION
  (with the Schema Delta as the proposal)
```

**Key Constraint:** After the pivot loop completes (confirmation → re-evaluation), the system ALWAYS returns to a card-based flow. The pivot is a short detour, not a mode change. The user never stays in open chat mode.

**UI Renders:** Confirmation card for the extracted delta:
```
Here's what I'm hearing from your update:

• New stakeholder introduced late
• Champion influence feels uncertain
• Decision process unclear

Does this reflect the situation?

[Yes, that's right]  [Adjust]  [Not really]
```

**Active Components:** Extraction Service (LLM), Confirmation Gate

**LLM Authority:** Extraction and translation only. Cannot determine strategy. Cannot remain in conversational mode.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| Schema delta extracted | AWAITING_CONFIRMATION |

---

### 11. SESSION_COMPLETE

**Purpose:** All structural patterns have been resolved. The deal is structurally sound based on lever states meeting exit conditions.

**Entry Condition:** Re-evaluation finds no active patterns with severity above threshold, or all exit conditions are satisfied.

**Data Flow:**
```
Final session state captured:
─ All lever states at target levels
─ Resolved patterns logged
─ Full interaction history preserved
```

**UI Renders:** Summary of the session — what was diagnosed, what strategy was executed, what changed.

**Active Components:** Explanation Service (for summary), Session Manager

**LLM Authority:** Summary generation only.

**Valid Transitions:**
| Trigger | Next State |
|---|---|
| User provides new information / deal changes | INTAKE (session re-opens) |

---

## State Transition Summary

| From | To | Trigger |
|---|---|---|
| NEW_SESSION | INTAKE | User provides first input |
| INTAKE | AWAITING_CONFIRMATION | Signals extracted / selected |
| INTAKE | INTAKE | General AI response (no state change) |
| AWAITING_CONFIRMATION | EVALUATING | User confirms, readiness met |
| AWAITING_CONFIRMATION | INTAKE | User confirms but readiness NOT met (gap remains) |
| AWAITING_CONFIRMATION | INTAKE | User rejects / adjusts |
| AWAITING_CONFIRMATION | PIVOT | User enters free text |
| EVALUATING | PRESENTING_DIAGNOSIS | DecisionResult produced |
| PRESENTING_DIAGNOSIS | ACTION_SELECTION | Single pattern, user confirms |
| PRESENTING_DIAGNOSIS | DUAL_PATTERN_TRADEOFF | Multiple patterns, user confirms |
| PRESENTING_DIAGNOSIS | INTAKE | User disagrees |
| PRESENTING_DIAGNOSIS | PIVOT | User enters free text |
| DUAL_PATTERN_TRADEOFF | ACTION_SELECTION | User picks approach |
| DUAL_PATTERN_TRADEOFF | PIVOT | User enters free text |
| ACTION_SELECTION | MONITORING | User selects action |
| ACTION_SELECTION | PIVOT | User enters free text |
| MONITORING | AWAITING_CONFIRMATION | User reports outcome |
| MONITORING | PIVOT | User enters free text |
| RE_EVALUATING | ACTION_SELECTION | Same strategy continues |
| RE_EVALUATING | PRESENTING_DIAGNOSIS | Strategy changed or pattern resolved |
| RE_EVALUATING | SESSION_COMPLETE | All patterns resolved |
| PIVOT | AWAITING_CONFIRMATION | Schema delta extracted |
| SESSION_COMPLETE | INTAKE | New information provided |

---

## Data Flow Through the Demo Scenario

Tracing the demo document through these states:

| Step | State | What Happens | Data Changed |
|---|---|---|---|
| 1 | NEW_SESSION | Sara opens Victros | Session created, all levers WEAK |
| 2 | INTAKE | Sara types deal description ("compliance director who likes Cyera...") | Input received |
| 3 | AWAITING_CONFIRMATION | System proposes situation summary, asks "Which of these best describes?" | — |
| 4 | INTAKE | System asks buying stage (button selection) | deal_snapshot.stage set |
| 5 | INTAKE | System asks about stakeholder alignment (button) | — |
| 6 | AWAITING_CONFIRMATION | System confirms "you're being pulled into validation without consensus" — asks to fix structure | — |
| 7 | INTAKE | System asks for deal snapshot (stage, close date, amount) + attachment | deal_snapshot populated |
| 8 | AWAITING_CONFIRMATION | System shows extracted deal snapshot, asks confirmation | deal_snapshot confirmed |
| 9 | INTAKE | Signal check — user taps: Single-Threaded, Competition, Validation Misalignment | signals selected |
| 10 | AWAITING_CONFIRMATION | Signals confirmed (button tap = direct confirmation) | active_signals updated |
| 11 | EVALUATING | Decision Engine runs | patterns + strategy_path computed |
| 12 | PRESENTING_DIAGNOSIS | Diagnosis: 3 patterns, recommends Selling_to_Consensus | User confirms |
| 13 | ACTION_SELECTION | "Ready to test your Champion?" — action: Champion test | User selects introduction to CISO |
| 14 | MONITORING | "Did your Champion complete the action?" | User reports yes |
| 15 | AWAITING_CONFIRMATION | Positive progress signal proposed | User confirms |
| 16 | RE_EVALUATING | Single-threaded risk partially resolved, consensus still needed | Strategy continues |
| 17 | ACTION_SELECTION | "Align full stakeholder group" — stakeholder mapping | User maps stakeholders |
| 18 | ACTION_SELECTION | Stakeholder criteria refinement | User adjusts priorities |
| 19 | ACTION_SELECTION | Consensus view confirmed, next strategic moves presented | User picks "connect solution to priorities" |
| 20 | ACTION_SELECTION | Which stakeholder first? | User picks — session continues |

---

## LLM Boundary Rules By State

| State | LLM Called? | What LLM Can Do | What LLM Cannot Do |
|---|---|---|---|
| NEW_SESSION | No | — | — |
| INTAKE | Yes (Intent Router, Extraction) | Classify input; extract candidate signals | Activate signals; determine strategy |
| AWAITING_CONFIRMATION | No | — | — |
| EVALUATING | No | — | — |
| PRESENTING_DIAGNOSIS | Yes (Explanation) | Translate diagnosis to coaching voice | Alter strategy; invent patterns |
| DUAL_PATTERN_TRADEOFF | Yes (Explanation) | Explain tradeoff pros/cons | Change priority pattern; invent options |
| ACTION_SELECTION | Yes (Explanation) | Describe actions in natural language | Invent actions outside schema |
| MONITORING | Yes (Explanation) | Frame the progress question | Interpret outcome strategically |
| RE_EVALUATING | No | — | — |
| PIVOT | Yes (Extraction) | Extract schema deltas from free text | Stay in chat mode; determine strategy |
| SESSION_COMPLETE | Yes (Explanation) | Generate session summary | — |
