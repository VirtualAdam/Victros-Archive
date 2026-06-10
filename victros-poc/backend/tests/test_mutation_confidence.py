"""Mutation confidence tests for the Victros decision engine.

Each test applies a single deliberate mutation via monkeypatch and verifies that
the engine produces a DIFFERENT result than the unmutated baseline. A passing
test means the mutation WAS detected (the test suite has coverage). A failing
test means the mutation went unnoticed (coverage gap).
"""
from __future__ import annotations

import pathlib
import pytest

from server.schema_store import SchemaStore
from server.decision_engine import DecisionEngine

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


@pytest.fixture
def schema():
    return SchemaStore(SCHEMA_DIR)


@pytest.fixture
def engine(schema):
    return DecisionEngine(schema)


def _run(engine, signals, stage="3_Validation"):
    """Helper: run engine and return a hashable summary tuple."""
    r = engine.run(active_signals=signals, deal_stage=stage)
    return (r.primary_pattern, tuple(sorted(r.secondary_patterns)), r.strategy_path)


# ── MUT-01: Swap lever order (decision_process ↔ buyer_consensus) ────────
class TestMut01LeverSwap:
    """Swapping lever positions 3 and 4 must change tiebreaker outcome."""

    # Activates 4 patterns all tied on weight(4.0)/severity(HIGH)/type(structural_risk):
    #   process_misalignment       → min lever = decision_process_alignment (idx 3)
    #   validation_disadvantage    → min lever = decision_process_alignment (idx 3)
    #   commodity_relegation       → min lever = buyer_consensus (idx 4)
    #   competitive_mindshare      → min lever = buyer_consensus (idx 4)
    # Swapping positions 3↔4 flips the winner from process_misalignment to
    # commodity_relegation.

    SIGNALS = [
        "validation_process_misalignment",  # HIGH structural_risk → process_misalignment, validation_disadvantage
        "competition_gaining_mindshare",    # HIGH structural_risk → competitive_mindshare, commodity_relegation
    ]

    def test_lever_swap_detected(self, monkeypatch, engine):
        import server.decision_engine as de

        baseline = _run(engine, self.SIGNALS)

        swapped = list(de.LEVER_ORDER)
        swapped[3], swapped[4] = swapped[4], swapped[3]
        monkeypatch.setattr(de, "LEVER_ORDER", swapped)

        mutated = _run(engine, self.SIGNALS)

        assert baseline != mutated, (
            "MUT-01: Lever order swap (decision_process ↔ buyer_consensus) "
            "was not detected — coverage gap"
        )


# ── MUT-02: Remove STRUCTURAL_BONUS ──────────────────────────────────────
class TestMut02StructuralBonus:
    """Setting STRUCTURAL_BONUS = 0 must change PatternWeight for patterns
    with structural signals."""

    # Mix structural and momentum signals targeting different patterns.
    # problem_not_validated (CRITICAL structural_risk) → weak_problem_definition
    # activity_without_progress (MEDIUM momentum_risk) → stagnant_deal
    # slowdowns_or_silence (MEDIUM momentum_risk) → momentum_loss
    SIGNALS = [
        "problem_not_validated",           # CRITICAL structural_risk
        "activity_without_progress",       # MEDIUM momentum_risk
        "slowdowns_or_silence",            # MEDIUM momentum_risk
    ]

    def test_structural_bonus_removal_detected(self, monkeypatch, engine):
        import server.decision_engine as de

        baseline_weights = self._get_weights(engine, de)

        monkeypatch.setattr(de, "STRUCTURAL_BONUS", 0)

        mutated_weights = self._get_weights(engine, de)

        assert baseline_weights != mutated_weights, (
            "MUT-02: Removing STRUCTURAL_BONUS was not detected — coverage gap"
        )

    def _get_weights(self, engine, de):
        signals = engine._resolve_signals(self.SIGNALS)
        activated = engine.activate_patterns_from_signals(signals)
        lever_states = engine.evaluate_signals(self.SIGNALS)
        return engine.compute_pattern_weights(activated, signals, lever_states)


# ── MUT-03: Remove LEVER_WEIGHT ──────────────────────────────────────────
class TestMut03LeverWeight:
    """Setting LEVER_WEIGHT = 0 must change PatternWeight for patterns
    targeting the weakest lever."""

    # All levers start WEAK; weakest = first in LEVER_ORDER = case_for_change_strength.
    # weak_problem_definition affects case_for_change_strength → gets lever bonus.
    # champion_absence affects champion_strength → no lever bonus.
    SIGNALS = [
        "problem_not_validated",       # → weak_problem_definition (lever: case_for_change)
        "no_named_or_active_champion", # → champion_absence (lever: champion_strength)
    ]

    def test_lever_weight_removal_detected(self, monkeypatch, engine):
        import server.decision_engine as de

        baseline_weights = self._get_weights(engine, de)

        monkeypatch.setattr(de, "LEVER_WEIGHT", 0)

        mutated_weights = self._get_weights(engine, de)

        assert baseline_weights != mutated_weights, (
            "MUT-03: Removing LEVER_WEIGHT was not detected — coverage gap"
        )

    def _get_weights(self, engine, de):
        signals = engine._resolve_signals(self.SIGNALS)
        activated = engine.activate_patterns_from_signals(signals)
        lever_states = engine.evaluate_signals(self.SIGNALS)
        return engine.compute_pattern_weights(activated, signals, lever_states)


# ── MUT-04: density_factor always returns 0 ──────────────────────────────
class TestMut04DensityFactor:
    """Zeroing density_factor must remove the multi-signal advantage."""

    # Use signals that converge on the same pattern to create density > 0.
    # validation_process_misalignment + no_differentiated_decision_criteria
    # + competition_gaining_mindshare all target commodity_relegation and/or
    # competitive_mindshare, giving those patterns density bonus.
    SIGNALS = [
        "validation_process_misalignment",    # → process_misalignment, validation_disadvantage
        "no_differentiated_decision_criteria", # → commodity_relegation, competitive_mindshare
        "competition_gaining_mindshare",       # → competitive_mindshare, commodity_relegation
    ]

    def test_density_factor_zero_detected(self, monkeypatch, engine):
        import server.decision_engine as de

        baseline_weights = self._get_weights(engine, de)

        monkeypatch.setattr(de, "density_factor", lambda n: 0.0)

        mutated_weights = self._get_weights(engine, de)

        assert baseline_weights != mutated_weights, (
            "MUT-04: Zeroing density_factor was not detected — coverage gap"
        )

    def _get_weights(self, engine, de):
        signals = engine._resolve_signals(self.SIGNALS)
        activated = engine.activate_patterns_from_signals(signals)
        lever_states = engine.evaluate_signals(self.SIGNALS)
        return engine.compute_pattern_weights(activated, signals, lever_states)


# ── MUT-05: Disable sufficiency check ────────────────────────────────────
class TestMut05SufficiencyDisabled:
    """Making sufficient_authority() always return True should allow
    patterns with a single LOW momentum signal through."""

    # responsiveness_velocity is MEDIUM momentum_strength → high_responsiveness_momentum.
    # A single MEDIUM momentum signal should NOT pass sufficiency (no structural,
    # and <2 HIGH/CRITICAL). With sufficiency disabled, it becomes primary.
    SIGNALS = ["responsiveness_velocity"]  # single MEDIUM momentum_strength

    def test_sufficiency_bypass_detected(self, monkeypatch, engine):
        import server.decision_engine as de

        baseline = engine.run(active_signals=self.SIGNALS, deal_stage="2_Evaluation")

        monkeypatch.setattr(
            de.DecisionEngine,
            "sufficient_authority",
            lambda self, pattern, signals: True,
        )

        mutated = engine.run(active_signals=self.SIGNALS, deal_stage="2_Evaluation")

        assert (baseline.primary_pattern != mutated.primary_pattern), (
            "MUT-05: Disabling sufficiency check was not detected — coverage gap"
        )


# ── MUT-06: Change activation from OR to AND ────────────────────────────
class TestMut06ActivationAndGate:
    """Requiring ALL signals in target_patterns (AND logic) instead of ANY
    should dramatically reduce pattern activation."""

    # Use multiple signals that each target different patterns.
    # Only one signal per pattern → AND gate means zero activations.
    SIGNALS = [
        "problem_not_validated",       # → weak_problem_definition
        "no_named_or_active_champion", # → champion_absence
        "no_eb_validation",            # → eb_alignment_gap
    ]

    def test_and_gate_detected(self, monkeypatch, engine):
        import server.decision_engine as de

        baseline = engine.run(active_signals=self.SIGNALS, deal_stage="2_Evaluation")
        assert baseline.primary_pattern is not None, "Baseline should have a primary pattern"

        def and_gate_activate(self_engine, signals):
            """Activate only if ALL signals for a pattern are present."""
            signal_keys = {s.key for s in signals}
            activated = []
            for pattern in self_engine.schema.patterns:
                pattern_signal_keys = set()
                for s in self_engine.schema.signals:
                    if pattern.key in s.target_patterns:
                        pattern_signal_keys.add(s.key)
                if pattern_signal_keys and pattern_signal_keys.issubset(signal_keys):
                    activated.append(pattern)
            return activated

        monkeypatch.setattr(
            de.DecisionEngine,
            "activate_patterns_from_signals",
            and_gate_activate,
        )

        mutated = engine.run(active_signals=self.SIGNALS, deal_stage="2_Evaluation")

        assert (
            baseline.primary_pattern != mutated.primary_pattern
            or set(baseline.secondary_patterns) != set(mutated.secondary_patterns)
        ), "MUT-06: AND-gating activation was not detected — coverage gap"


# ── MUT-07: Invert severity weights ─────────────────────────────────────
class TestMut07InvertSeverity:
    """Reversing severity weights (CRITICAL=1, LOW=4) should invert
    priority pattern selection."""

    # weak_problem_definition: CRITICAL, weight=6.0 (sev=4 + struct=1 + lever=1)
    # late_stakeholder_risk:    MEDIUM,   weight=3.0 (sev=2 + struct=1)
    # After inversion (CRITICAL=1, MEDIUM=3):
    # weak_problem_definition: weight=3.0 (sev=1 + struct=1 + lever=1)
    # late_stakeholder_risk:    weight=4.0 (sev=3 + struct=1)
    # → winner flips from weak_problem_definition to late_stakeholder_risk
    SIGNALS = [
        "problem_not_validated",         # CRITICAL structural_risk → weak_problem_definition
        "new_stakeholder_appears_late",  # MEDIUM structural_risk → late_stakeholder_risk
    ]

    def test_severity_inversion_detected(self, monkeypatch, engine):
        import server.decision_engine as de

        baseline = _run(engine, self.SIGNALS)

        monkeypatch.setattr(de, "SEVERITY_WEIGHT", {
            "CRITICAL": 1,
            "HIGH": 2,
            "MEDIUM": 3,
            "LOW": 4,
        })

        mutated = _run(engine, self.SIGNALS)

        assert baseline != mutated, (
            "MUT-07: Inverting severity weights was not detected — coverage gap"
        )


# ── MUT-08: Remove zone preference in strategy path selection ────────────
class TestMut08ZonePreference:
    """Zone bias is now a soft tiebreaker (confirmed by Richard, Apr 18).
    The structurally correct path (first in candidate list) must always
    win regardless of zone. This test verifies that the engine selects
    the first candidate even when it doesn't match the current zone."""

    SIGNALS = ["no_named_or_active_champion"]  # → champion_absence

    def test_zone_does_not_override_structural_path(self, engine):
        # champion_absence candidates: Identify_Champion_Targets first
        # Running in zone3 — Identify_Champion_Targets has zone_bias [zone1,2]
        # but must still be selected (structural correctness > zone match)
        result = engine.run(
            active_signals=self.SIGNALS, deal_stage="3_Validation"
        )
        assert result.strategy_path == "Identify_Champion_Targets", (
            f"Zone bias overrode structural path: got {result.strategy_path}"
        )


# ── MUT-09: Skip PatternWeight in priority selection ─────────────────────
class TestMut09SkipPatternWeight:
    """Using only pattern-level severity (ignoring PatternWeight) should
    change outcomes when signal authority disagrees with pattern severity."""

    # Mix signals so that PatternWeight diverges from pattern severity.
    # weak_problem_definition: CRITICAL severity, but few contributing signals
    # validation_disadvantage: HIGH severity, but 3 contributing signals → high weight
    SIGNALS = [
        "validation_process_misalignment",     # HIGH → process_misalignment, validation_disadvantage
        "no_differentiated_decision_criteria",  # MEDIUM → commodity_relegation, competitive_mindshare
        "competition_gaining_mindshare",        # HIGH → competitive_mindshare, commodity_relegation
        "buyer_objections_surfacing_early",     # MEDIUM → messaging_disconnect, weak_problem_definition
    ]

    def test_skip_pattern_weight_detected(self, monkeypatch, engine):
        import server.decision_engine as de

        baseline = _run(engine, self.SIGNALS)

        original_select = de.DecisionEngine.select_priority_pattern

        def select_severity_only(self_engine, patterns, weights):
            """Select using only pattern severity, ignoring PatternWeight."""
            zero_weights = {p.key: 0.0 for p in patterns}
            return original_select(self_engine, patterns, zero_weights)

        monkeypatch.setattr(
            de.DecisionEngine,
            "select_priority_pattern",
            select_severity_only,
        )

        mutated = _run(engine, self.SIGNALS)

        assert baseline != mutated, (
            "MUT-09: Skipping PatternWeight in priority selection "
            "was not detected — coverage gap"
        )
