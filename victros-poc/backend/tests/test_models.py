"""Tier 1 — Model Tests (M-01 → M-10).

Tests for Pydantic models defined in server.models.
These tests are written BEFORE the implementation exists.
Every test should FAIL until models.py is implemented.
"""
import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# M-01: Construct a Signal from valid JSON
# ---------------------------------------------------------------------------
class TestSignalModel:
    def test_m01_valid_signal(self):
        from server.models import Signal

        data = {
            "key": "single_threaded_contact",
            "name": "Single-Threaded Contact",
            "description": "Only one stakeholder is engaged.",
            "observable_condition": "All communication flows through a single contact.",
            "polarity": "negative",
            "severity": "HIGH",
            "type": "structural_risk",
            "affected_levers": ["champion_strength", "buyer_consensus"],
            "target_patterns": ["single_threaded_risk"],
        }
        signal = Signal(**data)
        assert signal.key == "single_threaded_contact"
        assert signal.polarity == "negative"
        assert signal.severity == "HIGH"
        assert signal.type == "structural_risk"
        assert "champion_strength" in signal.affected_levers
        assert len(signal.target_patterns) == 1

    # -----------------------------------------------------------------------
    # M-02: Missing required field raises ValidationError
    # -----------------------------------------------------------------------
    def test_m02_missing_required_field(self):
        from server.models import Signal

        data = {
            "key": "single_threaded_contact",
            # "name" is missing
            "description": "Only one stakeholder is engaged.",
            "observable_condition": "All communication flows through a single contact.",
            "polarity": "negative",
            "severity": "HIGH",
            "type": "structural_risk",
            "affected_levers": ["champion_strength"],
            "target_patterns": ["single_threaded_risk"],
        }
        with pytest.raises(ValidationError):
            Signal(**data)


# ---------------------------------------------------------------------------
# M-03: Construct a Pattern with trigger_signals
# ---------------------------------------------------------------------------
class TestPatternModel:
    def test_m03_valid_pattern(self):
        from server.models import Pattern

        data = {
            "key": "singlethreaded_risk",
            "name": "Single-Threaded Risk",
            "summary": "Only one stakeholder is engaged.",
            "trigger_signals": ["single_threaded_contact"],
            "diagnostic_questions": ["Who else has direct knowledge?"],
            "root_cause_themes": ["access_limitation"],
            "polarity": "negative",
            "type": "structural_risk",
            "severity": "HIGH",
            "resolution_type": "RECOVER",
            "zone_bias": ["zone2"],
            "affected_levers": ["champion_strength", "buyer_consensus"],
            "candidate_strategy_path_keys": ["Selling_to_Consensus"],
        }
        pattern = Pattern(**data)
        assert pattern.key == "singlethreaded_risk"
        assert pattern.trigger_signals == ["single_threaded_contact"]
        assert pattern.resolution_type == "RECOVER"
        assert len(pattern.candidate_strategy_path_keys) == 1


# ---------------------------------------------------------------------------
# M-04: Construct a StrategyPath with full schema
# ---------------------------------------------------------------------------
class TestStrategyPathModel:
    def test_m04_valid_strategy_path(self):
        from server.models import StrategyPath

        data = {
            "key": "Selling_to_Consensus",
            "display_name": "Consensus Not Yet Aligned",
            "description": "Stakeholder alignment is insufficient to support a viable decision path.",
            "mode": "RECOVER",
            "diagnostic_question": "Is decision support distributed across the full buying group?",
            "activation_polarity": "NO_ACTIVATES_PATH",
            "target_levers": ["buyer_consensus", "champion_strength"],
            "dominant_failure_mode": "Single-threaded engagement collapses without broad commitment.",
            "zone_bias": ["zone2", "zone3"],
            "primary_target_pattern": "singlethreaded_risk",
            "entry_conditions": ["Consensus is limited to one or two stakeholders"],
            "disqualifying_conditions": ["Multiple stakeholders are actively aligned"],
            "core_objectives": "Expand stakeholder alignment across the buying group.",
            "strategic_focus": "Broaden engagement and validate commitment.",
            "core_strategies": ["Champion-led introductions", "Persona-specific outreach"],
            "prohibited_strategies": ["Bypassing champion"],
            "representative_actions": ["explain_why_alignment_across_the_full_stakeholder"],
            "positive_progress_signals": ["multi_threading_momentum"],
            "negative_progress_signals": ["activity_without_progress"],
            "exit_lever_state": "buyer_consensus=COMMITTED",
            "exit_outcome": "Multiple stakeholders confirm aligned criteria",
            "transition_signals": [],
            "operator_notes": "",
        }
        sp = StrategyPath(**data)
        assert sp.key == "Selling_to_Consensus"
        assert sp.mode == "RECOVER"
        assert sp.entry_conditions == ["Consensus is limited to one or two stakeholders"]
        assert sp.disqualifying_conditions == ["Multiple stakeholders are actively aligned"]
        assert sp.positive_progress_signals == ["multi_threading_momentum"]
        assert sp.negative_progress_signals == ["activity_without_progress"]
        assert sp.exit_lever_state == "buyer_consensus=COMMITTED"


# ---------------------------------------------------------------------------
# M-05: Construct a Lever with state enum
# ---------------------------------------------------------------------------
class TestLeverModel:
    def test_m05_valid_lever(self):
        from server.models import Lever

        data = {
            "key": "champion_strength",
            "name": "Champion Strength",
            "description": "Measures the champion's ability to drive the deal.",
            "states": ["WEAK", "CONNECTED", "COMMITTED", "EXECUTING"],
        }
        lever = Lever(**data)
        assert lever.key == "champion_strength"
        assert lever.states == ["WEAK", "CONNECTED", "COMMITTED", "EXECUTING"]

    def test_m05_invalid_state_value(self):
        from server.models import LeverState

        with pytest.raises(ValueError):
            LeverState("INVALID")


# ---------------------------------------------------------------------------
# M-06: Construct a SalesZone
# ---------------------------------------------------------------------------
class TestSalesZoneModel:
    def test_m06_valid_zone(self):
        from server.models import SalesZone

        data = {
            "key": "zone1",
            "display_name": "Early Stage - Discovery / Pre-Qualification",
            "buyer_type": "Prospect",
            "purpose": "Qualify a winnable deal.",
            "qualification_requirements": ["Identify_Problems", "Metrics"],
        }
        zone = SalesZone(**data)
        assert zone.key == "zone1"
        assert zone.display_name == "Early Stage - Discovery / Pre-Qualification"
        assert len(zone.qualification_requirements) == 2


# ---------------------------------------------------------------------------
# M-07: DealSnapshot with optional fields missing
# ---------------------------------------------------------------------------
class TestDealSnapshotModel:
    def test_m07_optional_fields(self):
        from server.models import DealSnapshot

        # Only stage is required for the Decision Engine to run
        snap = DealSnapshot(stage="3_Validation")
        assert snap.stage == "3_Validation"
        assert snap.close_date is None
        assert snap.amount is None
        assert snap.notes is None

    def test_m07_full_snapshot(self):
        from server.models import DealSnapshot

        snap = DealSnapshot(
            stage="3_Validation",
            close_date="2026-06-30",
            amount=1200000,
            notes="Compliance-led initiative",
        )
        assert snap.amount == 1200000


# ---------------------------------------------------------------------------
# M-08: DecisionResult dataclass
# ---------------------------------------------------------------------------
class TestDecisionResultModel:
    def test_m08_valid_result(self):
        from server.models import DecisionResult

        result = DecisionResult(
            primary_pattern="single_threaded_risk",
            secondary_patterns=["competitive_displacement"],
            strategy_path="selling_to_consensus",
            representative_actions=["run_persona_discussions"],
            active_signals=["single_threaded_contact"],
            lever_states={
                "case_for_change_strength": "WEAK",
                "champion_strength": "CONNECTED",
                "economic_buyer_commitment": "WEAK",
                "buyer_consensus": "WEAK",
                "decision_process_alignment": "WEAK",
                "differentiation_leverage": "WEAK",
                "buyer_urgency": "WEAK",
            },
            zone="zone_2_mid_stage",
        )
        assert result.primary_pattern == "single_threaded_risk"
        assert result.zone == "zone_2_mid_stage"
        assert len(result.lever_states) == 7


# ---------------------------------------------------------------------------
# M-09: SessionState serializes to JSON and back
# ---------------------------------------------------------------------------
class TestSessionStateModel:
    def test_m09_round_trip(self):
        from server.models import SessionState

        data = {
            "session_id": "test-uuid-001",
            "user_id": "user_001",
            "opportunity_id": "opp_acme_001",
            "state": "NEW_SESSION",
            "deal_snapshot": None,
            "active_signals": [],
            "active_patterns": {"primary": None, "secondary": []},
            "selected_strategy_path": None,
            "lever_states": {
                "case_for_change_strength": "WEAK",
                "champion_strength": "WEAK",
                "economic_buyer_commitment": "WEAK",
                "buyer_consensus": "WEAK",
                "decision_process_alignment": "WEAK",
                "differentiation_leverage": "WEAK",
                "buyer_urgency": "WEAK",
            },
            "interaction_history": [],
            "intake_readiness": {
                "deal_stage": "missing",
                "deal_close_date": "missing",
                "deal_amount": "missing",
                "deal_notes": "missing",
                "signals_confirmed": False,
            },
        }
        session = SessionState(**data)
        json_str = session.model_dump_json()
        restored = SessionState.model_validate_json(json_str)
        assert restored.session_id == session.session_id
        assert restored.lever_states == session.lever_states
        assert restored.intake_readiness == session.intake_readiness


# ---------------------------------------------------------------------------
# M-11: ActiveSignal model (SRS 1.6 — system-derived signal metadata)
# ---------------------------------------------------------------------------
class TestActiveSignalModel:
    def test_m11_valid_construction(self):
        from server.models import ActiveSignal

        sig = ActiveSignal(
            key="single_threaded_contact",
            confidence=0.85,
            evidence_text="Only one contact in CRM",
            source="system",
        )
        assert sig.key == "single_threaded_contact"
        assert sig.confidence == 0.85
        assert sig.evidence_text == "Only one contact in CRM"
        assert sig.source == "system"

    def test_m11_defaults(self):
        from server.models import ActiveSignal

        sig = ActiveSignal(key="champion_coaching_influence")
        assert sig.confidence == 0.0
        assert sig.evidence_text is None
        assert sig.source == "system"

    def test_m11_user_override_source(self):
        from server.models import ActiveSignal

        sig = ActiveSignal(
            key="economic_buyer_engagement",
            confidence=1.0,
            source="user_override",
        )
        assert sig.source == "user_override"

    def test_m11_round_trip_json(self):
        from server.models import ActiveSignal

        sig = ActiveSignal(
            key="problem_not_validated",
            confidence=0.92,
            evidence_text="No ROI quantified",
            source="system",
        )
        json_str = sig.model_dump_json()
        restored = ActiveSignal.model_validate_json(json_str)
        assert restored.key == sig.key
        assert restored.confidence == sig.confidence
        assert restored.evidence_text == sig.evidence_text
        assert restored.source == sig.source


# ---------------------------------------------------------------------------
# M-12: Signal model extended fields (SRS 1.2, 1.8)
# ---------------------------------------------------------------------------
class TestSignalExtendedFields:
    def test_m12_confidence_threshold_default(self):
        from server.models import Signal

        data = {
            "key": "test_signal",
            "name": "Test Signal",
            "description": "A test signal.",
            "observable_condition": "Test condition.",
            "polarity": "negative",
            "severity": "HIGH",
            "type": "structural_risk",
            "affected_levers": ["champion_strength"],
        }
        signal = Signal(**data)
        assert signal.confidence_threshold == 0.0
        assert signal.requires_evidence is False

    def test_m12_confidence_threshold_set(self):
        from server.models import Signal

        data = {
            "key": "test_signal",
            "name": "Test Signal",
            "description": "A test signal.",
            "observable_condition": "Test condition.",
            "polarity": "negative",
            "severity": "CRITICAL",
            "type": "structural_risk",
            "affected_levers": ["champion_strength"],
            "confidence_threshold": 0.7,
            "requires_evidence": True,
        }
        signal = Signal(**data)
        assert signal.confidence_threshold == 0.7
        assert signal.requires_evidence is True


# ---------------------------------------------------------------------------
# M-10: IntakeReadiness defaults
# ---------------------------------------------------------------------------
class TestIntakeReadinessModel:
    def test_m10_defaults(self):
        from server.models import IntakeReadiness

        readiness = IntakeReadiness()
        assert readiness.deal_stage == "missing"
        assert readiness.deal_close_date == "missing"
        assert readiness.deal_amount == "missing"
        assert readiness.deal_notes == "missing"
        assert readiness.signals_confirmed is False


# ---------------------------------------------------------------------------
# M-13: DecisionSnapshot model (Phase 6 — per-evaluation decision snapshots)
# ---------------------------------------------------------------------------
class TestDecisionSnapshotModel:
    def test_m13_valid_construction(self):
        from server.models import DecisionSnapshot

        snap = DecisionSnapshot(
            snapshot_id="snap-test-001",
            session_id="sess-001",
            user_id="user_001",
            opportunity_id="opp_001",
            evaluation_run_id=1,
            timestamp="2025-07-14T12:00:00Z",
            active_signals=[{"key": "single_threaded_contact", "confidence": 0.85}],
            lever_states={
                "champion_strength": "WEAK",
                "economic_buyer_access": "WEAK",
                "case_for_change_strength": "WEAK",
                "buyer_urgency": "WEAK",
                "decision_process_control": "WEAK",
            },
            primary_pattern="single_threaded_risk",
            secondary_patterns=["competitive_displacement"],
            selected_strategy_path="selling_to_consensus",
            selected_action="run_persona_discussions",
            signal_quality_warnings=["low_confidence_signal"],
        )
        assert snap.snapshot_id == "snap-test-001"
        assert snap.evaluation_run_id == 1
        assert snap.opportunity_id == "opp_001"
        assert len(snap.active_signals) == 1
        assert snap.signal_quality_warnings == ["low_confidence_signal"]

    def test_m13_defaults(self):
        from server.models import DecisionSnapshot

        snap = DecisionSnapshot(
            snapshot_id="snap-test-002",
            session_id="sess-002",
            user_id="user_001",
            opportunity_id="opp_002",
            evaluation_run_id=1,
            timestamp="2025-07-14T12:00:00Z",
            active_signals=[],
            lever_states={},
            primary_pattern=None,
            secondary_patterns=[],
        )
        assert snap.selected_strategy_path is None
        assert snap.selected_action is None
        assert snap.signal_quality_warnings == []

    def test_m13_evaluation_run_id_is_int(self):
        from server.models import DecisionSnapshot

        snap = DecisionSnapshot(
            snapshot_id="snap-test-003",
            session_id="sess-003",
            user_id="user_001",
            opportunity_id="opp_003",
            evaluation_run_id=1,
            timestamp="2025-07-14T12:00:00Z",
            active_signals=[],
            lever_states={},
            primary_pattern=None,
            secondary_patterns=[],
        )
        assert isinstance(snap.evaluation_run_id, int)
        assert snap.evaluation_run_id >= 1
