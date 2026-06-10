"""Pydantic models for all Victros SRS data types."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class LeverState(str, Enum):
    WEAK = "WEAK"
    CONNECTED = "CONNECTED"
    COMMITTED = "COMMITTED"
    EXECUTING = "EXECUTING"


class SessionStateEnum(str, Enum):
    NEW_SESSION = "NEW_SESSION"
    INTENT_CAPTURE = "INTENT_CAPTURE"
    SITUATION_VALIDATION = "SITUATION_VALIDATION"
    INTAKE = "INTAKE"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    EVALUATING = "EVALUATING"
    PATTERN_DIAGNOSTICS = "PATTERN_DIAGNOSTICS"
    PRESENTING_DIAGNOSIS = "PRESENTING_DIAGNOSIS"
    ALIGNMENT_CHECKPOINT = "ALIGNMENT_CHECKPOINT"
    DUAL_PATTERN_TRADEOFF = "DUAL_PATTERN_TRADEOFF"
    ACTION_SELECTION = "ACTION_SELECTION"
    MONITORING = "MONITORING"
    RE_EVALUATING = "RE_EVALUATING"
    SESSION_PAUSED = "SESSION_PAUSED"
    SESSION_COMPLETE = "SESSION_COMPLETE"


# ---------------------------------------------------------------------------
# Schema models (loaded from JSON files)
# ---------------------------------------------------------------------------
class Signal(BaseModel):
    key: str
    name: str
    description: str
    observable_condition: str
    polarity: str  # "positive" | "negative"
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    type: str  # "structural_risk" | "momentum_risk" | "structural_strength" | "momentum_strength"
    affected_levers: list[str]
    zone_bias: list[str] = []
    trigger_input_conditions: str = ""
    target_patterns: list[str] = []
    confidence_threshold: float = 0.0
    requires_evidence: bool = False
    calibration_note: str = ""


class ActiveSignal(BaseModel):
    """A signal that has been derived/activated with metadata."""
    key: str
    confidence: float = 0.0  # 0.0-1.0
    evidence_text: str | None = None
    source: str = "system"  # "system" | "user_override"


class Pattern(BaseModel):
    key: str
    name: str
    description: str = ""
    summary: str
    trigger_signals: list[str]
    diagnostic_questions: list[str]
    root_cause_themes: list[str]
    polarity: str
    type: str
    severity: str
    resolution_type: str  # "RECOVER" | "ADVANCE" | "EXIT"
    zone_bias: list[str] = []
    affected_levers: list[str]
    candidate_strategy_path_keys: list[str]


class StrategyPath(BaseModel):
    key: str
    display_name: str
    description: str
    mode: str  # "RECOVER" | "ADVANCE" | "EXIT"
    diagnostic_question: str
    activation_polarity: str
    target_levers: list[str]
    dominant_failure_mode: str
    zone_bias: list[str] = []
    primary_target_pattern: str
    target_patterns: list[str] = []
    entry_conditions: list[str]
    disqualifying_conditions: list[str]
    core_objectives: str = ""
    strategic_focus: str = ""
    core_strategies: list[str]
    prohibited_strategies: list[str]
    representative_actions: list[str]
    champion_required_behavior: str = ""
    economic_buyer_required_behavior: str = ""
    positive_progress_signals: list[str]
    negative_progress_signals: list[str]
    exit_lever_state: str = ""
    exit_outcome: str = ""
    transition_signals: list[str] = []
    operator_notes: str = ""


class Lever(BaseModel):
    key: str
    name: str
    qualifiers: str = ""
    score_model: str = ""
    lever_scoring: str = ""
    why_it_matters: str = ""
    states: list[str]


class SalesZone(BaseModel):
    key: str
    display_name: str
    buyer_type: str = ""
    purpose: str = ""
    core_objectives: str = ""
    core_strategies: str = ""
    strategy_method: str = ""
    core_actions: str = ""
    minimum_required_lever_states: str = ""
    zone_risk_lever_triggers: str = ""
    qualification_requirements: list[str] = []
    qualification_guidance: str = ""


class RepresentativeAction(BaseModel):
    action_key: str
    parent_strategy_path: str
    description: str
    ux_text: str
    specificity: str = "generic"  # "generic" | "situation-specific"


# ---------------------------------------------------------------------------
# Session / runtime models
# ---------------------------------------------------------------------------
class DealSnapshot(BaseModel):
    stage: str
    close_date: str | None = None
    amount: float | None = None
    notes: str | None = None


class IntakeReadiness(BaseModel):
    deal_stage: str = "missing"
    offering_type: str = "missing"
    offering_usage: str = "missing"
    usage_depth: str = "missing"
    deal_amount: str = "missing"
    deal_close_date: str = "missing"
    deal_notes: str = "missing"
    signals_confirmed: bool = False


class ActivePatterns(BaseModel):
    primary: str | None = None
    secondary: list[str] = []


class DecisionSnapshot(BaseModel):
    """Per-evaluation snapshot captured each time the decision engine runs."""
    snapshot_id: str
    session_id: str
    user_id: str
    opportunity_id: str
    evaluation_run_id: int
    timestamp: str
    active_signals: list[dict] = []
    lever_states: dict[str, str] = {}
    primary_pattern: str | None = None
    secondary_patterns: list[str] = []
    selected_strategy_path: str | None = None
    selected_action: str | None = None
    signal_quality_warnings: list = []


class SessionState(BaseModel):
    session_id: str
    user_id: str
    opportunity_id: str
    state: str = "NEW_SESSION"
    intent_text: str | None = None
    deal_snapshot: DealSnapshot | None = None
    active_signals: list[str] = []
    active_patterns: ActivePatterns = ActivePatterns()
    selected_strategy_path: str | None = None
    lever_states: dict[str, str] = {}
    interaction_history: list[dict[str, Any]] = []
    intake_readiness: IntakeReadiness = IntakeReadiness()
    # Persisted IntakeTracker state: {"fields": {...}, "active_signals": [...]}
    intake_fields: dict[str, Any] = {}
    selected_action_key: str | None = None
    continuation_options: list[str] = []
    excluded_patterns: list[str] = []
    decision_snapshots: list[DecisionSnapshot] = []
    created_at: str | None = None
    updated_at: str | None = None


class MonitoringTriggerConditions(BaseModel):
    """Defines what triggers re-evaluation in monitoring state."""
    transition_signals: list[str] = []
    negative_progress_detected: bool = True
    user_requested: bool = True
    max_idle_turns: int = 3


class DecisionResult(BaseModel):
    primary_pattern: str | None
    secondary_patterns: list[str]
    strategy_path: str | None
    representative_actions: list[str]
    active_signals: list[str]
    lever_states: dict[str, str]
    zone: str
    signal_quality_warnings: list[dict[str, Any]] = []
    gap_blocked: bool = False
