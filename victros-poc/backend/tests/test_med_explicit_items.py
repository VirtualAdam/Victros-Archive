"""Phase 7 — MED-priority Explicit Items (1.5, 1.8, 1.10, 1.13, 1.14, 1.15, 1.17, 1.19).

TDD tests for 8 medium-priority items from Richard's SRS feedback.
"""
from __future__ import annotations

import pathlib
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


@pytest.fixture
def schema_store():
    from server.schema_store import SchemaStore
    return SchemaStore(SCHEMA_DIR)


@pytest.fixture
def engine(schema_store):
    from server.decision_engine import DecisionEngine
    return DecisionEngine(schema_store)


# ═══════════════════════════════════════════════════════════════════════════
# 1.5 — Confidence Calibration Notes
# Each signal should have a calibration_note field explaining what
# HIGH vs LOW confidence means for that signal.
# ═══════════════════════════════════════════════════════════════════════════
class TestConfidenceCalibrationNotes:
    def test_signal_model_has_calibration_note(self):
        from server.models import Signal
        sig = Signal(
            key="test_signal",
            name="Test Signal",
            description="desc",
            observable_condition="cond",
            polarity="negative",
            severity="HIGH",
            type="structural_risk",
            affected_levers=["champion_strength"],
            calibration_note="HIGH = buyer explicitly named; LOW = inferred from role title",
        )
        assert sig.calibration_note == "HIGH = buyer explicitly named; LOW = inferred from role title"

    def test_signal_calibration_note_defaults_empty(self):
        from server.models import Signal
        sig = Signal(
            key="test_signal",
            name="Test Signal",
            description="desc",
            observable_condition="cond",
            polarity="negative",
            severity="HIGH",
            type="structural_risk",
            affected_levers=["champion_strength"],
        )
        assert sig.calibration_note == ""

    def test_schema_signals_have_calibration_notes(self, schema_store):
        """At least some schema signals should have non-empty calibration notes."""
        notes = [s.calibration_note for s in schema_store.signals if s.calibration_note]
        assert len(notes) >= 5, "At least 5 signals should have calibration notes"


# ═══════════════════════════════════════════════════════════════════════════
# 1.8 — Signal-to-Lever Mapping Traceability
# Expose which lever each signal maps to in the evaluation result.
# ═══════════════════════════════════════════════════════════════════════════
class TestSignalToLeverMapping:
    def test_engine_has_signal_lever_map_method(self, engine):
        """Engine should produce a mapping of signal_key -> affected_levers."""
        mapping = engine.build_signal_lever_map(
            ["single_threaded_contact", "champion_coaching_influence"]
        )
        assert "single_threaded_contact" in mapping
        assert "buyer_consensus" in mapping["single_threaded_contact"]
        assert "champion_strength" in mapping["champion_coaching_influence"]

    def test_signal_lever_map_empty_signals(self, engine):
        mapping = engine.build_signal_lever_map([])
        assert mapping == {}


# ═══════════════════════════════════════════════════════════════════════════
# 1.10 — Evaluation Transparency Summary
# After evaluation, provide a human-readable summary of why patterns
# were activated and strategy was selected.
# ═══════════════════════════════════════════════════════════════════════════
class TestEvaluationTransparencySummary:
    def test_generate_transparency_summary(self, engine):
        result = engine.run(
            ["single_threaded_contact", "no_named_or_active_champion"],
            deal_stage="zone2",
        )
        summary = engine.generate_transparency_summary(result)
        assert isinstance(summary, str)
        assert len(summary) > 20
        # Should mention the primary pattern
        if result.primary_pattern:
            assert result.primary_pattern in summary

    def test_transparency_summary_no_pattern(self, engine):
        result = engine.run([], deal_stage="zone2")
        summary = engine.generate_transparency_summary(result)
        assert "no patterns" in summary.lower() or "no active" in summary.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 1.13 — Full Lever Coverage Check
# Verify all 7 levers have at least one signal; warn if not.
# ═══════════════════════════════════════════════════════════════════════════
class TestFullLeverCoverageCheck:
    def test_check_lever_coverage_full(self, engine):
        """With the full schema, all 7 levers should be covered."""
        result = engine.check_lever_coverage()
        assert result["covered"] is True
        assert len(result["uncovered_levers"]) == 0

    def test_check_lever_coverage_warns_if_missing(self, schema_store):
        """If signals are filtered to not cover a lever, should warn."""
        from server.decision_engine import DecisionEngine
        eng = DecisionEngine(schema_store)
        # Check with a subset of signals that might not cover all levers
        result = eng.check_lever_coverage(
            signal_keys=["problem_not_validated"]
        )
        # problem_not_validated affects case_for_change_strength and buyer_urgency
        assert len(result["uncovered_levers"]) > 0
        assert result["covered"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 1.14 — Pattern Activation Trace
# Show which signals triggered which patterns in the evaluation result.
# ═══════════════════════════════════════════════════════════════════════════
class TestPatternActivationTrace:
    def test_pattern_activation_trace(self, engine):
        result = engine.run(
            ["single_threaded_contact", "no_named_or_active_champion"],
            deal_stage="zone2",
        )
        trace = engine.build_pattern_activation_trace(
            ["single_threaded_contact", "no_named_or_active_champion"]
        )
        assert isinstance(trace, dict)
        # Each activated pattern should map to its triggering signals
        for pattern_key, triggering_signals in trace.items():
            assert isinstance(triggering_signals, list)
            assert len(triggering_signals) >= 1

    def test_trace_empty_signals(self, engine):
        trace = engine.build_pattern_activation_trace([])
        assert trace == {}


# ═══════════════════════════════════════════════════════════════════════════
# 1.15 — Action Specificity Labels
# Actions should have specificity metadata (generic vs situation-specific).
# ═══════════════════════════════════════════════════════════════════════════
class TestActionSpecificityLabels:
    def test_action_model_has_specificity(self):
        from server.models import RepresentativeAction
        action = RepresentativeAction(
            action_key="test_action",
            parent_strategy_path="test_sp",
            description="Test action",
            ux_text="Do the thing",
            specificity="situation-specific",
        )
        assert action.specificity == "situation-specific"

    def test_action_specificity_defaults_generic(self):
        from server.models import RepresentativeAction
        action = RepresentativeAction(
            action_key="test_action",
            parent_strategy_path="test_sp",
            description="Test action",
            ux_text="Do the thing",
        )
        assert action.specificity == "generic"

    def test_schema_actions_have_specificity(self, schema_store):
        """All schema actions should have a specificity field."""
        for action in schema_store.representative_actions:
            assert action.specificity in ("generic", "situation-specific")


# ═══════════════════════════════════════════════════════════════════════════
# 1.17 — Session History Diffing
# Ability to compare two evaluation snapshots within a session.
# ═══════════════════════════════════════════════════════════════════════════
class TestSessionHistoryDiffing:
    def test_diff_snapshots_basic(self):
        from server.decision_engine import diff_snapshots
        snap_a = {
            "active_signals": ["single_threaded_contact"],
            "lever_states": {"champion_strength": "WEAK", "buyer_consensus": "WEAK"},
            "primary_pattern": "singlethreaded_risk",
            "strategy_path": "Qualify_CaseForChange",
        }
        snap_b = {
            "active_signals": ["single_threaded_contact", "champion_coaching_influence"],
            "lever_states": {"champion_strength": "CONNECTED", "buyer_consensus": "WEAK"},
            "primary_pattern": "singlethreaded_risk",
            "strategy_path": "Qualify_CaseForChange",
        }
        diff = diff_snapshots(snap_a, snap_b)
        assert "signals_added" in diff
        assert "champion_coaching_influence" in diff["signals_added"]
        assert "lever_changes" in diff
        assert diff["lever_changes"]["champion_strength"] == {"before": "WEAK", "after": "CONNECTED"}

    def test_diff_snapshots_pattern_change(self):
        from server.decision_engine import diff_snapshots
        snap_a = {"primary_pattern": "singlethreaded_risk", "active_signals": [], "lever_states": {}}
        snap_b = {"primary_pattern": "champion_absence", "active_signals": [], "lever_states": {}}
        diff = diff_snapshots(snap_a, snap_b)
        assert diff["primary_pattern_changed"] is True
        assert diff["primary_pattern"] == {"before": "singlethreaded_risk", "after": "champion_absence"}


# ═══════════════════════════════════════════════════════════════════════════
# 1.19 — Monitoring Trigger Conditions
# Define what triggers re-evaluation in monitoring state.
# ═══════════════════════════════════════════════════════════════════════════
class TestMonitoringTriggerConditions:
    def test_monitoring_trigger_conditions_model(self):
        from server.models import MonitoringTriggerConditions
        triggers = MonitoringTriggerConditions(
            transition_signals=["competition_gaining_mindshare"],
            negative_progress_detected=True,
            user_requested=True,
            max_idle_turns=3,
        )
        assert triggers.transition_signals == ["competition_gaining_mindshare"]
        assert triggers.negative_progress_detected is True
        assert triggers.max_idle_turns == 3

    def test_should_trigger_re_evaluation_on_transition_signal(self, engine):
        from server.decision_engine import should_trigger_re_evaluation
        sp = engine.schema.get_strategy_path("Qualify_CaseForChange")
        assert sp is not None
        # Transition signals should trigger re-evaluation
        if sp.transition_signals:
            result = should_trigger_re_evaluation(
                strategy_path=sp,
                new_signals=sp.transition_signals[:1],
                progress_status="neutral",
            )
            assert result["should_re_evaluate"] is True
            assert "transition_signal_match" in result["reasons"]

    def test_should_trigger_on_negative_progress(self, engine):
        from server.decision_engine import should_trigger_re_evaluation
        sp = engine.schema.get_strategy_path("Qualify_CaseForChange")
        assert sp is not None
        result = should_trigger_re_evaluation(
            strategy_path=sp,
            new_signals=[],
            progress_status="negative",
        )
        assert result["should_re_evaluate"] is True
        assert "negative_progress" in result["reasons"]

    def test_should_not_trigger_when_stable(self, engine):
        from server.decision_engine import should_trigger_re_evaluation
        sp = engine.schema.get_strategy_path("Qualify_CaseForChange")
        assert sp is not None
        result = should_trigger_re_evaluation(
            strategy_path=sp,
            new_signals=[],
            progress_status="positive",
        )
        assert result["should_re_evaluate"] is False
