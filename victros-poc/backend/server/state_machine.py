"""State Machine — valid transition definitions.

Encodes the full state transition table from data-flow-logic.md Part 1.
States S1–S12 map the Strategic Interaction Model (Spec §3.0).

Two-Loop Architecture (§3.0)
============================

The state machine implements two distinct loops that together form the
Strategic Interaction Model:

**Loop 1 — Initial Evaluation (intake → first action)**
    NEW_SESSION → INTENT_CAPTURE → SITUATION_VALIDATION → INTAKE →
    AWAITING_CONFIRMATION → EVALUATING → PATTERN_DIAGNOSTICS →
    PRESENTING_DIAGNOSIS → ALIGNMENT_CHECKPOINT → ACTION_SELECTION →
    MONITORING

    This loop runs once per deal engagement.  It collects signals, runs the
    decision engine, diagnoses the primary pattern, verifies alignment with
    the user, and selects an initial strategy/action.

**Loop 2 — Monitoring / Re-evaluation (ongoing)**
    MONITORING → RE_EVALUATING → PRESENTING_DIAGNOSIS →
    ALIGNMENT_CHECKPOINT → ACTION_SELECTION → MONITORING

    After the initial action is selected the user enters the monitoring
    loop.  From MONITORING the user can:
      • *continue*     — stay in MONITORING (no state change)
      • *re_evaluate*   — transition to RE_EVALUATING, then cycle back
      • *address_next_issue* — exclude current pattern, re-run engine,
                               present the next pattern via Loop 1 tail
      • *exit_for_now*  — transition to SESSION_PAUSED (can resume later)

    SESSION_PAUSED → MONITORING resumes the monitoring loop.
    SESSION_COMPLETE is the terminal state.
"""
from __future__ import annotations

# Valid transitions: { from_state: [to_state, ...] }
VALID_TRANSITIONS: dict[str, list[str]] = {
    # S1: Session created → intent capture
    "NEW_SESSION": ["INTENT_CAPTURE"],
    # S2: Intent captured → situation validation
    "INTENT_CAPTURE": ["SITUATION_VALIDATION"],
    # S3: Situation validated → intake; correction → re-capture
    "SITUATION_VALIDATION": ["INTAKE", "INTENT_CAPTURE"],
    # S4: Intake complete → awaiting confirmation
    "INTAKE": ["AWAITING_CONFIRMATION"],
    # S5: Confirmed → evaluating; adjust/reject → intake
    "AWAITING_CONFIRMATION": ["EVALUATING", "INTAKE"],
    # S6: Engine complete → pattern diagnostics
    "EVALUATING": ["PATTERN_DIAGNOSTICS", "INTAKE"],
    # S7: Patterns confirmed → diagnosis; rejected → intake
    "PATTERN_DIAGNOSTICS": ["PRESENTING_DIAGNOSIS", "INTAKE"],
    # S8: Understanding confirmed → alignment checkpoint
    "PRESENTING_DIAGNOSIS": ["ALIGNMENT_CHECKPOINT"],
    # S8b: Alignment checkpoint → action selection, dual pattern, intake (re-entry), or stay
    "ALIGNMENT_CHECKPOINT": ["ACTION_SELECTION", "DUAL_PATTERN_TRADEOFF", "INTAKE", "ALIGNMENT_CHECKPOINT"],
    # S9: Tradeoff resolved → action selection
    "DUAL_PATTERN_TRADEOFF": ["ACTION_SELECTION"],
    # S10: Action selected → monitoring (active strategy state)
    "ACTION_SELECTION": ["MONITORING"],
    # S11: Next decision from monitoring
    "MONITORING": ["MONITORING", "RE_EVALUATING", "SESSION_COMPLETE", "SESSION_PAUSED", "ALIGNMENT_CHECKPOINT"],
    # S12: Re-evaluation complete → presenting diagnosis or monitoring
    "RE_EVALUATING": ["PRESENTING_DIAGNOSIS", "MONITORING", "SESSION_COMPLETE"],
    # Paused → resume monitoring or start new
    "SESSION_PAUSED": ["MONITORING", "INTENT_CAPTURE"],
    # Terminal → can start new deal
    "SESSION_COMPLETE": ["INTENT_CAPTURE"],
}


def validate_transition(from_state: str, to_state: str) -> bool:
    """Return True if the transition is valid, False otherwise."""
    allowed = VALID_TRANSITIONS.get(from_state, [])
    return to_state in allowed
