"""Phase 2 — Signal Quality Gates (QG-01 → QG-07).

Tests for detect_signal_gaps() and its integration with DecisionEngine.run().
Gap detection identifies levers with zero active-signal coverage and blocks
pattern prioritization when critical coverage gaps exist.
"""
from __future__ import annotations

import pathlib

import pytest

from server.models import ActiveSignal, DecisionResult

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


@pytest.fixture
def schema_store():
    from server.schema_store import SchemaStore

    return SchemaStore(SCHEMA_DIR)


@pytest.fixture
def engine(schema_store):
    from server.decision_engine import DecisionEngine

    return DecisionEngine(schema_store)


# Helper: build a minimal set of signal keys that covers every lever.
# One positive + one negative per lever to avoid polarity imbalance.
def _all_levers_covered_signals() -> list[str]:
    """Signal keys that together cover all 7 levers."""
    return [
        # case_for_change_strength  (pos: usage_demonstrates_material_value, neg: problem_not_validated)
        "usage_demonstrates_material_value",
        "problem_not_validated",
        # champion_strength  (pos: champion_coaching_influence, neg: no_named_or_active_champion)
        "champion_coaching_influence",
        "no_named_or_active_champion",
        # economic_buyer_commitment  (pos: economic_buyer_engagement, neg: no_eb_validation)
        "economic_buyer_engagement",
        "no_eb_validation",
        # decision_process_alignment  (pos: adoption_conversion_momentum, neg: validation_process_misalignment)
        "adoption_conversion_momentum",
        "validation_process_misalignment",
        # buyer_consensus  (covered by champion_coaching_influence + no_named_or_active_champion above)
        # differentiation_leverage  (pos: differentiated_validation_momentum, neg: competition_gaining_mindshare)
        "differentiated_validation_momentum",
        "competition_gaining_mindshare",
        # buyer_urgency  (pos: responsiveness_velocity, neg: slowdowns_or_silence)
        "responsiveness_velocity",
        "slowdowns_or_silence",
    ]


# ═══════════════════════════════════════════════════════════════════════════
# QG-01: All levers covered → no gap warnings
# ═══════════════════════════════════════════════════════════════════════════

class TestAllLeversCoveredPassesGate:
    def test_qg01_all_levers_covered_passes_gate(self, schema_store):
        from server.decision_engine import detect_signal_gaps

        active = _all_levers_covered_signals()
        gaps = detect_signal_gaps(active, schema_store)
        assert gaps == []


# ═══════════════════════════════════════════════════════════════════════════
# QG-02: Missing lever coverage raises gap
# ═══════════════════════════════════════════════════════════════════════════

class TestMissingLeverCoverageRaisesGap:
    def test_qg02_missing_lever_coverage_raises_gap(self, schema_store):
        from server.decision_engine import detect_signal_gaps

        # Provide signals that cover everything EXCEPT economic_buyer_commitment
        active = [
            "usage_demonstrates_material_value",
            "problem_not_validated",
            "champion_coaching_influence",
            "no_named_or_active_champion",
            "adoption_conversion_momentum",
            "validation_process_misalignment",
            "differentiated_validation_momentum",
            "competition_gaining_mindshare",
            "responsiveness_velocity",
            "slowdowns_or_silence",
        ]
        gaps = detect_signal_gaps(active, schema_store)
        uncovered = [g for g in gaps if g["gap_type"] == "uncovered"]
        assert len(uncovered) >= 1
        lever_names = [g["lever_name"] for g in uncovered]
        assert "economic_buyer_commitment" in lever_names


# ═══════════════════════════════════════════════════════════════════════════
# QG-03: Critical gap blocks pattern prioritization
# ═══════════════════════════════════════════════════════════════════════════

class TestCriticalGapBlocksPatternPrioritization:
    def test_qg03_critical_gap_blocks_pattern_prioritization(self, engine, schema_store):
        """When a lever with CRITICAL-severity signals has zero coverage,
        run() should return gap_blocked=True and empty patterns/strategy."""
        from server.decision_engine import detect_signal_gaps

        # Only cover differentiation_leverage (no CRITICAL signals) — leave
        # all levers with CRITICAL signals uncovered.
        active = ["differentiated_validation_momentum", "competition_gaining_mindshare"]

        # Verify gaps are detected
        gaps = detect_signal_gaps(active, schema_store)
        critical_gaps = [g for g in gaps if g["gap_type"] == "uncovered"
                         and g.get("severity") == "critical"]
        assert len(critical_gaps) > 0, "Should detect critical-lever gaps"

        # run() should block
        result = engine.run(active, deal_stage="2_Qualification", enforce_quality_gates=True)
        assert result.gap_blocked is True
        assert result.primary_pattern is None
        assert result.strategy_path is None
        assert len(result.signal_quality_warnings) > 0


# ═══════════════════════════════════════════════════════════════════════════
# QG-04: Non-critical gap warns but continues
# ═══════════════════════════════════════════════════════════════════════════

class TestNonCriticalGapWarnsButContinues:
    def test_qg04_non_critical_gap_warns_but_continues(self, engine, schema_store):
        """When only differentiation_leverage is uncovered (no CRITICAL signals),
        run() should warn but NOT block."""
        from server.decision_engine import detect_signal_gaps

        # Cover all levers EXCEPT differentiation_leverage — use only signals
        # whose affected_levers do NOT include differentiation_leverage.
        active = [
            "usage_demonstrates_material_value",   # case_for_change_strength (pos)
            "problem_not_validated",                # case_for_change_strength, buyer_urgency (neg)
            "champion_coaching_influence",           # champion_strength, buyer_consensus (pos)
            "no_named_or_active_champion",           # champion_strength, buyer_consensus (neg)
            "economic_buyer_engagement",             # economic_buyer_commitment, buyer_consensus (pos)
            "no_eb_validation",                      # economic_buyer_commitment, buyer_consensus (neg)
            "adoption_conversion_momentum",          # champion_strength, decision_process_alignment (pos)
            "new_stakeholder_appears_late",           # buyer_consensus, decision_process_alignment (neg)
            "responsiveness_velocity",               # buyer_urgency, champion_strength (pos)
            "slowdowns_or_silence",                  # buyer_urgency, champion_strength (neg)
        ]
        gaps = detect_signal_gaps(active, schema_store)
        uncovered = [g for g in gaps if g["gap_type"] == "uncovered"]
        assert any(g["lever_name"] == "differentiation_leverage" for g in uncovered)

        result = engine.run(active, deal_stage="2_Qualification", enforce_quality_gates=True)
        assert result.gap_blocked is False
        assert len(result.signal_quality_warnings) > 0


# ═══════════════════════════════════════════════════════════════════════════
# QG-05: Polarity imbalance warning
# ═══════════════════════════════════════════════════════════════════════════

class TestPolarityImbalance:
    def test_qg05_gap_detection_considers_polarity_balance(self, schema_store):
        """A lever covered only by negative signals (no positive)
        should generate a polarity_imbalance warning."""
        from server.decision_engine import detect_signal_gaps

        # Cover champion_strength with ONLY negative signals.
        # Avoid responsiveness_velocity and adoption_conversion_momentum which
        # are positive and also affect champion_strength.
        active = [
            "no_named_or_active_champion",   # negative, champion_strength + buyer_consensus
            "single_threaded_contact",        # negative, champion_strength + buyer_consensus
            # Cover other levers fully (positive + negative) to isolate
            "usage_demonstrates_material_value",   # pos, case_for_change_strength
            "problem_not_validated",               # neg, case_for_change_strength + buyer_urgency
            "economic_buyer_engagement",            # pos, economic_buyer_commitment + buyer_consensus
            "no_eb_validation",                     # neg, economic_buyer_commitment + buyer_consensus
            "adoption_without_decision_formation",  # neg, decision_process_alignment + buyer_urgency
            "new_stakeholder_appears_late",          # neg, buyer_consensus + decision_process_alignment
            "differentiated_validation_momentum",   # pos, differentiation_leverage + case_for_change_strength
            "competition_gaining_mindshare",         # neg, differentiation_leverage + buyer_consensus
            "outcomes_unclear_or_misaligned",        # neg, case_for_change_strength + buyer_urgency
        ]
        gaps = detect_signal_gaps(active, schema_store)
        imbalance = [g for g in gaps if g["gap_type"] == "polarity_imbalance"]
        lever_names = [g["lever_name"] for g in imbalance]
        assert "champion_strength" in lever_names


# ═══════════════════════════════════════════════════════════════════════════
# QG-06: Gap report shape
# ═══════════════════════════════════════════════════════════════════════════

class TestGapReportShape:
    def test_qg06_gap_report_shape(self, schema_store):
        """Each gap dict must include lever_name, gap_type, and missing_signal_keys."""
        from server.decision_engine import detect_signal_gaps

        # Remove economic_buyer_commitment coverage
        active = [
            "usage_demonstrates_material_value",
            "problem_not_validated",
            "champion_coaching_influence",
            "no_named_or_active_champion",
            "adoption_conversion_momentum",
            "validation_process_misalignment",
            "differentiated_validation_momentum",
            "competition_gaining_mindshare",
            "responsiveness_velocity",
            "slowdowns_or_silence",
        ]
        gaps = detect_signal_gaps(active, schema_store)
        eb_gap = [g for g in gaps if g["lever_name"] == "economic_buyer_commitment"]
        assert len(eb_gap) == 1
        gap = eb_gap[0]

        assert "lever_name" in gap
        assert gap["gap_type"] in ("uncovered", "polarity_imbalance")
        assert "missing_signal_keys" in gap
        assert isinstance(gap["missing_signal_keys"], list)
        assert len(gap["missing_signal_keys"]) > 0
        # economic_buyer_engagement and no_eb_validation should be suggested
        assert "economic_buyer_engagement" in gap["missing_signal_keys"]
        assert "no_eb_validation" in gap["missing_signal_keys"]


# ═══════════════════════════════════════════════════════════════════════════
# QG-07: Gate integrates with engine.run()
# ═══════════════════════════════════════════════════════════════════════════

class TestGateIntegratesWithEngineRun:
    def test_qg07_gate_integrates_with_engine_run(self, engine):
        """Full run() with a critical gap → gap_blocked=True and warnings."""
        active = ["differentiated_validation_momentum", "competition_gaining_mindshare"]
        result = engine.run(active, deal_stage="2_Qualification", enforce_quality_gates=True)
        assert result.gap_blocked is True
        assert result.primary_pattern is None
        assert result.strategy_path is None
        assert isinstance(result.signal_quality_warnings, list)
        assert len(result.signal_quality_warnings) > 0
        # Warnings should be dicts with expected shape
        for w in result.signal_quality_warnings:
            assert "lever_name" in w
            assert "gap_type" in w
