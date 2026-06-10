"""Golden tests from Richard Rivera's UAT diary — HIS expected outcomes.

These tests encode Richard's actual observations and expectations from UAT
testing, not our interpretation of the spec. When a test fails, the engine
disagrees with Richard's expected outcome.

Sources:
  - inputs/comms/Victors POC UAT Diary_  Richard Rivera (RR).md
  - inputs/comms/wedemail.md (email validation request)
"""
import pathlib

import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


@pytest.fixture(scope="module")
def engine():
    from server.decision_engine import DecisionEngine
    from server.schema_store import SchemaStore

    store = SchemaStore(SCHEMA_DIR)
    return DecisionEngine(store)


# ═══════════════════════════════════════════════════════════════════════════
# Deal 1: TMobile_test  (UAT Diary Logic #3 — Apr 13)
#
# Primary Pattern: weak_problem_definition
# Secondary Pattern: champion_absence
# Expected StrategyPath: Qualify_CaseForChange
# BUG FOUND: System incorrectly routed to "Consensus Not Yet Aligned"
# ═══════════════════════════════════════════════════════════════════════════
class TestDeal1_TMobile:
    """TMobile_test: weak problem + champion absence → Qualify_CaseForChange."""

    SIGNALS = ["problem_not_validated", "no_named_or_active_champion"]
    STAGE = "3_Validation"

    def test_primary_is_weak_problem(self, engine):
        """Primary must be weak_problem_definition, not consensus-related."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.primary_pattern == "weak_problem_definition", (
            f"Expected primary_pattern='weak_problem_definition', "
            f"got '{result.primary_pattern}'"
        )

    def test_champion_absence_is_secondary(self, engine):
        """champion_absence must appear in secondary_patterns."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert "champion_absence" in result.secondary_patterns, (
            f"Expected 'champion_absence' in secondary_patterns, "
            f"got {result.secondary_patterns}"
        )

    def test_strategy_path_is_qualify_case_for_change(self, engine):
        """StrategyPath must be Qualify_CaseForChange.

        Richard confirmed: zone_bias must never override the structurally
        correct StrategyPath. It is a soft tiebreaker only.
        """
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.strategy_path == "Qualify_CaseForChange", (
            f"Expected strategy_path='Qualify_CaseForChange', "
            f"got '{result.strategy_path}'"
        )

    def test_not_consensus_pattern(self, engine):
        """Must NOT route to any consensus-related pattern as primary."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.primary_pattern is not None
        assert "consensus" not in result.primary_pattern.lower(), (
            f"Primary pattern must not be consensus-related, "
            f"got '{result.primary_pattern}'"
        )

    def test_unqualified_deal_not_primary(self, engine):
        """unqualified_deal should not win over weak_problem_definition.

        Both signals target unqualified_deal, but weak_problem_definition
        should win because it is the more specific structural pattern that
        problem_not_validated directly targets.
        """
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.primary_pattern != "unqualified_deal", (
            f"unqualified_deal should not be primary — "
            f"weak_problem_definition is the expected winner"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Deal 2: Problem Not Validated + Outcome Misalignment
#
# From Richard's email validation request (wedemail.md, Apr 14-15):
#   "re-run the recent test cases (e.g. Problem Not Validated + Outcome
#    Misalignment) and confirm: a single Priority Pattern is selected,
#    a single StrategyPath is selected"
# ═══════════════════════════════════════════════════════════════════════════
class TestDeal2_ProblemAndOutcome:
    """Problem Not Validated + Outcome Misalignment → single pattern + path."""

    SIGNALS = ["problem_not_validated", "outcomes_unclear_or_misaligned"]
    STAGE = "2_Qualification"

    def test_exactly_one_primary_pattern(self, engine):
        """Must select exactly one primary pattern."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.primary_pattern is not None, "No primary pattern selected"

    def test_exactly_one_strategy_path(self, engine):
        """Must select exactly one strategy path."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.strategy_path is not None, "No strategy path selected"

    def test_strategy_path_from_primary_pattern_candidates(self, engine):
        """StrategyPath must come from the primary pattern's candidates."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        # Look up the primary pattern's candidate strategy paths
        pattern = None
        for p in engine.schema.patterns:
            if p.key == result.primary_pattern:
                pattern = p
                break
        assert pattern is not None, f"Pattern '{result.primary_pattern}' not in schema"
        assert result.strategy_path in pattern.candidate_strategy_path_keys, (
            f"strategy_path '{result.strategy_path}' not in "
            f"primary pattern's candidates: {pattern.candidate_strategy_path_keys}"
        )

    def test_primary_pattern_is_structural(self, engine):
        """Both signals are structural_risk — primary should be structural."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        pattern = None
        for p in engine.schema.patterns:
            if p.key == result.primary_pattern:
                pattern = p
                break
        assert pattern is not None
        assert pattern.type == "structural_risk", (
            f"Expected structural_risk pattern, got '{pattern.type}'"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Deal 3: Signal Authority Drives Pattern Prioritization
#
# From UAT Diary Logic #4 (Apr 14-15):
#   "Signals were being treated as neutral inputs — signal authority
#    disappears after activation"
#   Fix: signal authority (severity, type, lever impact) must flow
#   into pattern prioritization
# ═══════════════════════════════════════════════════════════════════════════
class TestDeal3_SignalAuthorityPrinciple:
    """CRITICAL structural signal must outrank MEDIUM momentum signal."""

    def test_critical_structural_beats_medium_momentum(self, engine):
        """A CRITICAL structural signal's pattern must win over MEDIUM momentum.

        problem_not_validated (CRITICAL/structural_risk) → weak_problem_definition
        activity_without_progress (MEDIUM/momentum_risk) → stagnant_deal
        """
        result = engine.run(
            active_signals=["problem_not_validated", "activity_without_progress"],
            deal_stage="2_Qualification",
        )
        assert result.primary_pattern == "weak_problem_definition", (
            f"CRITICAL structural pattern should win — "
            f"got '{result.primary_pattern}' instead of 'weak_problem_definition'"
        )

    def test_critical_structural_beats_medium_structural(self, engine):
        """CRITICAL structural must beat MEDIUM structural (late_stakeholder_risk)."""
        result = engine.run(
            active_signals=["no_named_or_active_champion", "new_stakeholder_appears_late"],
            deal_stage="3_Validation",
        )
        # no_named_or_active_champion is CRITICAL → champion_absence (CRITICAL)
        # new_stakeholder_appears_late is MEDIUM → late_stakeholder_risk (MEDIUM)
        assert result.primary_pattern == "champion_absence", (
            f"CRITICAL should beat MEDIUM — "
            f"got '{result.primary_pattern}' instead of 'champion_absence'"
        )

    def test_pattern_weight_reflects_severity(self, engine):
        """PatternWeight must incorporate signal severity, not just count."""
        from server.decision_engine import SEVERITY_WEIGHT

        signals = engine._resolve_signals(
            ["problem_not_validated", "activity_without_progress"]
        )
        activated = engine.activate_patterns_from_signals(signals)
        lever_states = engine.evaluate_signals(
            ["problem_not_validated", "activity_without_progress"]
        )
        weights = engine.compute_pattern_weights(activated, signals, lever_states)

        # weak_problem_definition should have higher weight than stagnant_deal
        wpd = weights.get("weak_problem_definition", 0)
        sd = weights.get("stagnant_deal", 0)
        assert wpd > sd, (
            f"weak_problem_definition weight ({wpd}) should exceed "
            f"stagnant_deal weight ({sd})"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Deal 4: Apr 13 Six-Signal Complex Deal
#
# From UAT Diary Logic #3 + #6:
#   "With six active signals in the test deal"
#   System incorrectly routed: "New Stakeholder > EB Alignment gap (wrong)
#   / mixed with a Champion Testing Strategy Path (wrong)"
#
# The highest-authority signals must drive pattern selection.
# ═══════════════════════════════════════════════════════════════════════════
class TestDeal4_SixSignalComplex:
    """Six-signal deal: highest-authority signal must drive primary pattern."""

    SIGNALS = [
        "new_stakeholder_appears_late",
        "no_eb_validation",
        "no_named_or_active_champion",
        "single_threaded_contact",
        "competition_gaining_mindshare",
        "validation_process_misalignment",
    ]
    STAGE = "3_Validation"

    def test_primary_not_late_stakeholder(self, engine):
        """late_stakeholder_risk (MEDIUM) must NOT be primary with CRITICAL signals present."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.primary_pattern != "late_stakeholder_risk", (
            f"late_stakeholder_risk is MEDIUM — should not be primary "
            f"when CRITICAL signals (no_eb_validation, no_named_or_active_champion) are active"
        )

    def test_primary_is_critical_severity(self, engine):
        """Primary pattern must have CRITICAL severity (from CRITICAL signals)."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        pattern = None
        for p in engine.schema.patterns:
            if p.key == result.primary_pattern:
                pattern = p
                break
        assert pattern is not None, f"Pattern '{result.primary_pattern}' not found"
        assert pattern.severity == "CRITICAL", (
            f"Primary pattern severity should be CRITICAL, "
            f"got '{pattern.severity}' for '{result.primary_pattern}'"
        )

    def test_strategy_path_from_primary_candidates(self, engine):
        """StrategyPath must come from primary pattern's candidate list."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        pattern = None
        for p in engine.schema.patterns:
            if p.key == result.primary_pattern:
                pattern = p
                break
        assert pattern is not None
        assert result.strategy_path in pattern.candidate_strategy_path_keys, (
            f"strategy_path '{result.strategy_path}' not in "
            f"primary pattern '{result.primary_pattern}' candidates: "
            f"{pattern.candidate_strategy_path_keys}"
        )

    def test_has_multiple_secondary_patterns(self, engine):
        """Six signals should activate multiple patterns — not just one."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert len(result.secondary_patterns) >= 3, (
            f"Expected ≥3 secondary patterns from 6 signals, "
            f"got {len(result.secondary_patterns)}: {result.secondary_patterns}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Deal 5: PLG / Usage Deal
#
# From UAT Diary Logic #1 (Apr 14-15):
#   "I did a deal test where the product was in active usage (such as PLG,
#    pilot, freemium, customer). I selected this signal and yet the system
#    failed to respond with this context."
#
# Signal: adoption_without_decision_formation (CRITICAL/structural_risk)
# Target patterns: stagnant_deal, process_misalignment
# ═══════════════════════════════════════════════════════════════════════════
class TestDeal5_PLGUsage:
    """PLG/usage deal: adoption signal must activate relevant patterns."""

    SIGNALS = ["adoption_without_decision_formation"]
    STAGE = "1_Discovery"

    def test_activates_adoption_related_patterns(self, engine):
        """Must activate stagnant_deal or process_misalignment (signal targets)."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.primary_pattern is not None, (
            "System must respond to adoption_without_decision_formation — "
            "Richard reported it 'failed to respond with this context'"
        )
        adoption_patterns = {"stagnant_deal", "process_misalignment"}
        assert result.primary_pattern in adoption_patterns, (
            f"Expected primary pattern in {adoption_patterns}, "
            f"got '{result.primary_pattern}'"
        )

    def test_has_strategy_path(self, engine):
        """System must prescribe a strategy path for adoption signals."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        assert result.strategy_path is not None, (
            "No strategy path — Richard reported the system 'failed to respond'"
        )

    def test_strategy_path_from_candidates(self, engine):
        """StrategyPath must come from the activated pattern's candidates."""
        result = engine.run(active_signals=self.SIGNALS, deal_stage=self.STAGE)
        if result.primary_pattern is None or result.strategy_path is None:
            pytest.skip("No pattern/path selected — covered by other tests")
        pattern = None
        for p in engine.schema.patterns:
            if p.key == result.primary_pattern:
                pattern = p
                break
        assert pattern is not None
        assert result.strategy_path in pattern.candidate_strategy_path_keys, (
            f"strategy_path '{result.strategy_path}' not in "
            f"pattern '{result.primary_pattern}' candidates: "
            f"{pattern.candidate_strategy_path_keys}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Cross-cutting invariants Richard explicitly called out
# ═══════════════════════════════════════════════════════════════════════════
class TestRichardInvariants:
    """Invariants Richard stated must hold across ALL deals."""

    def test_single_primary_pattern_always(self, engine):
        """Spec sect 1.6: exactly one Priority Pattern selected.

        Richard: 'a single Priority Pattern is selected'
        """
        test_cases = [
            (["problem_not_validated"], "1_Discovery"),
            (["no_named_or_active_champion"], "2_Qualification"),
            (["problem_not_validated", "no_named_or_active_champion"], "3_Validation"),
            (["problem_not_validated", "outcomes_unclear_or_misaligned"], "2_Qualification"),
        ]
        for signals, stage in test_cases:
            result = engine.run(active_signals=signals, deal_stage=stage)
            assert result.primary_pattern is not None, (
                f"No primary pattern for signals={signals}, stage={stage}"
            )

    def test_single_strategy_path_always(self, engine):
        """Spec enforcement: exactly one StrategyPath selected.

        Richard: 'a single StrategyPath is selected'
        """
        test_cases = [
            (["problem_not_validated"], "1_Discovery"),
            (["no_named_or_active_champion"], "2_Qualification"),
            (["problem_not_validated", "no_named_or_active_champion"], "3_Validation"),
        ]
        for signals, stage in test_cases:
            result = engine.run(active_signals=signals, deal_stage=stage)
            assert result.strategy_path is not None, (
                f"No strategy path for signals={signals}, stage={stage}"
            )

    def test_strategy_path_always_from_primary_candidates(self, engine):
        """StrategyPath must always come from the primary pattern's candidate list."""
        test_cases = [
            (["problem_not_validated"], "1_Discovery"),
            (["no_named_or_active_champion"], "2_Qualification"),
            (["problem_not_validated", "no_named_or_active_champion"], "3_Validation"),
            (["adoption_without_decision_formation"], "1_Discovery"),
        ]
        for signals, stage in test_cases:
            result = engine.run(active_signals=signals, deal_stage=stage)
            if result.primary_pattern is None or result.strategy_path is None:
                continue
            pattern = None
            for p in engine.schema.patterns:
                if p.key == result.primary_pattern:
                    pattern = p
                    break
            assert pattern is not None
            assert result.strategy_path in pattern.candidate_strategy_path_keys, (
                f"[signals={signals}] strategy_path '{result.strategy_path}' "
                f"not in primary '{result.primary_pattern}' candidates"
            )
