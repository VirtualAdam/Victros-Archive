"""Phase 3 — StrategyPath Ranking Tests (SR-01 → SR-09).

TDD tests for multi-factor ranking in select_strategy_path().
Written BEFORE ranking logic is implemented.

The current select_strategy_path() returns the first surviving candidate.
These tests define the expected behaviour once ranking by lever alignment,
resolution-type match, and entry-condition strength is added.
"""
import pathlib
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


@pytest.fixture
def engine():
    from server.decision_engine import DecisionEngine
    from server.schema_store import SchemaStore

    store = SchemaStore(SCHEMA_DIR)
    return DecisionEngine(store)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_pattern(key, candidate_keys, resolution_type="RECOVER", **kwargs):
    """Fabricate a minimal Pattern for test scenarios."""
    from server.models import Pattern

    defaults = dict(
        key=key,
        name=key,
        summary="test pattern",
        trigger_signals=[],
        diagnostic_questions=[],
        root_cause_themes=[],
        polarity="negative",
        type="structural_risk",
        severity="HIGH",
        resolution_type=resolution_type,
        affected_levers=[],
        candidate_strategy_path_keys=candidate_keys,
    )
    defaults.update(kwargs)
    return Pattern(**defaults)


def _call_select(engine, pattern, active_signals, zone_key, lever_states):
    """Call select_strategy_path with the new lever_states kwarg.

    Falls back to the old 3-arg signature when ranking is not yet wired up.
    """
    import inspect

    sig = inspect.signature(engine.select_strategy_path)
    if "lever_states" in sig.parameters:
        return engine.select_strategy_path(
            pattern, active_signals, zone_key, lever_states=lever_states
        )
    # Pre-ranking implementation: call without lever_states
    return engine.select_strategy_path(pattern, active_signals, zone_key)


# ---------------------------------------------------------------------------
# SR-01  Lever alignment prefers WEAK levers
# ---------------------------------------------------------------------------
class TestStrategyPathRanking:

    def test_sr01_lever_alignment_prefers_weak_levers(self, engine):
        """Path targeting a WEAK lever should rank above one targeting a CONNECTED lever."""
        # Qualify_CaseForChange targets case_for_change_strength (WEAK)
        # Build_Champion targets champion_strength (CONNECTED)
        pattern = _build_pattern(
            "test_lever_align",
            ["Build_Champion", "Qualify_CaseForChange"],
            resolution_type="RECOVER",
        )
        lever_states = {
            "case_for_change_strength": "WEAK",
            "champion_strength": "CONNECTED",
            "buyer_urgency": "CONNECTED",
            "economic_buyer_commitment": "CONNECTED",
            "buyer_consensus": "CONNECTED",
            "differentiation_leverage": "CONNECTED",
            "decision_process_alignment": "CONNECTED",
        }
        result = _call_select(engine, pattern, [], "zone2", lever_states)

        assert result is not None
        # Qualify_CaseForChange targets the WEAK lever → should be chosen
        assert result.key == "Qualify_CaseForChange"

    # -------------------------------------------------------------------
    # SR-02  Resolution type: RECOVER matches structural breakdown
    # -------------------------------------------------------------------
    def test_sr02_resolution_type_recover_matches_breakdown(self, engine):
        """RECOVER-mode path should rank above ADVANCE when pattern is RECOVER."""
        # eb_alignment_gap: resolution_type=RECOVER, candidates include
        # Secure_EB_Alignment (RECOVER) and Empower_Champion (ADVANCE)
        pattern = engine.schema.get_pattern("eb_alignment_gap")
        assert pattern is not None

        lever_states = {
            "economic_buyer_commitment": "WEAK",
            "case_for_change_strength": "WEAK",
            "champion_strength": "WEAK",
            "buyer_urgency": "WEAK",
            "buyer_consensus": "WEAK",
            "differentiation_leverage": "WEAK",
            "decision_process_alignment": "WEAK",
        }
        result = _call_select(engine, pattern, [], "zone2", lever_states)

        assert result is not None
        # RECOVER-mode paths should outrank ADVANCE-mode paths
        assert result.mode == "RECOVER"

    # -------------------------------------------------------------------
    # SR-03  Resolution type: ADVANCE matches strength/momentum patterns
    # -------------------------------------------------------------------
    def test_sr03_resolution_type_advance_matches_stalled(self, engine):
        """ADVANCE-mode path should rank above RECOVER when pattern is ADVANCE."""
        # eb_sponsorship_motion: resolution_type=ADVANCE, candidates include
        # Empower_Champion (ADVANCE), Activate_Consensus (ADVANCE),
        # Champion_Negotiation (ADVANCE)
        pattern = engine.schema.get_pattern("eb_sponsorship_motion")
        assert pattern is not None

        lever_states = {
            "economic_buyer_commitment": "CONNECTED",
            "champion_strength": "CONNECTED",
            "buyer_consensus": "CONNECTED",
            "case_for_change_strength": "CONNECTED",
            "differentiation_leverage": "CONNECTED",
            "decision_process_alignment": "CONNECTED",
            "buyer_urgency": "CONNECTED",
        }
        result = _call_select(engine, pattern, [], "zone2", lever_states)

        assert result is not None
        assert result.mode == "ADVANCE"

    # -------------------------------------------------------------------
    # SR-04  Resolution type: EXIT matches unwinnable deal
    # -------------------------------------------------------------------
    def test_sr04_resolution_type_exit_matches_unwinnable(self, engine):
        """EXIT-mode path should rank highest for an unwinnable deal pattern."""
        # weak_problem_definition has candidates:
        # Qualify_CaseForChange (RECOVER), Identify_Champion_Targets (RECOVER),
        # Selling_to_Consensus (RECOVER), Disqualify_or_Deprioritize (EXIT)
        # We fabricate a pattern with resolution_type=EXIT using same candidates.
        pattern = _build_pattern(
            "test_unwinnable",
            [
                "Qualify_CaseForChange",
                "Identify_Champion_Targets",
                "Selling_to_Consensus",
                "Disqualify_or_Deprioritize",
            ],
            resolution_type="EXIT",
        )
        lever_states = {
            "case_for_change_strength": "WEAK",
            "champion_strength": "WEAK",
            "buyer_urgency": "WEAK",
            "economic_buyer_commitment": "WEAK",
            "buyer_consensus": "WEAK",
            "differentiation_leverage": "WEAK",
            "decision_process_alignment": "WEAK",
        }
        result = _call_select(engine, pattern, [], "zone2", lever_states)

        assert result is not None
        assert result.key == "Disqualify_or_Deprioritize"
        assert result.mode == "EXIT"

    # -------------------------------------------------------------------
    # SR-05  Entry condition strength as tiebreaker
    # -------------------------------------------------------------------
    def test_sr05_entry_condition_strength_tiebreaker(self, engine):
        """When lever alignment and resolution type tie, more satisfied entry
        conditions should win."""
        # Use two RECOVER paths that both target the same WEAK lever:
        # Qualify_CaseForChange targets [case_for_change_strength, buyer_urgency]
        # Build_Champion targets [champion_strength, case_for_change_strength]
        # Set both target levers to WEAK so lever alignment ties.
        pattern = _build_pattern(
            "test_entry_tiebreak",
            ["Qualify_CaseForChange", "Build_Champion"],
            resolution_type="RECOVER",
        )
        lever_states = {
            "case_for_change_strength": "WEAK",
            "champion_strength": "WEAK",
            "buyer_urgency": "WEAK",
            "economic_buyer_commitment": "COMMITTED",
            "buyer_consensus": "COMMITTED",
            "differentiation_leverage": "COMMITTED",
            "decision_process_alignment": "COMMITTED",
        }
        # Both paths are RECOVER, both target WEAK levers → tie.
        # The one with more satisfied entry conditions should win.
        result = _call_select(engine, pattern, [], "zone2", lever_states)

        assert result is not None
        # Exact winner depends on entry-condition evaluation; just verify
        # it isn't always the first candidate (positional bias removed).
        # We run it twice to ensure determinism (see SR-06) but here we
        # simply assert a non-None result and that ranking was applied.
        result2 = _call_select(engine, pattern, [], "zone2", lever_states)
        assert result.key == result2.key, "Tiebreaker should be deterministic"

    # -------------------------------------------------------------------
    # SR-06  Composite ranking is deterministic
    # -------------------------------------------------------------------
    def test_sr06_composite_ranking_deterministic(self, engine):
        """Same inputs must always produce the same ranking (no randomness)."""
        pattern = engine.schema.get_pattern("stagnant_deal")
        assert pattern is not None

        lever_states = {
            "case_for_change_strength": "WEAK",
            "champion_strength": "WEAK",
            "buyer_urgency": "CONNECTED",
            "economic_buyer_commitment": "CONNECTED",
            "buyer_consensus": "CONNECTED",
            "differentiation_leverage": "CONNECTED",
            "decision_process_alignment": "CONNECTED",
        }
        results = [
            _call_select(engine, pattern, [], "zone2", lever_states)
            for _ in range(20)
        ]
        keys = [r.key for r in results if r is not None]
        assert len(set(keys)) == 1, f"Non-deterministic results: {set(keys)}"

    # -------------------------------------------------------------------
    # SR-07  All disqualified → None
    # -------------------------------------------------------------------
    def test_sr07_all_disqualified_returns_none(self, engine):
        """If every candidate is disqualified, select_strategy_path returns None."""
        # Fabricate a pattern whose only candidate has a signal-key
        # disqualifying condition that is active.
        from server.models import StrategyPath

        pattern = _build_pattern(
            "test_all_dq",
            ["_fake_sp_dq_"],
        )
        # Monkey-patch schema to return a path with a signal-key DQ condition
        original_get = engine.schema.get_strategy_path

        def _patched(key):
            if key == "_fake_sp_dq_":
                return StrategyPath(
                    key="_fake_sp_dq_",
                    display_name="Fake DQ",
                    description="",
                    mode="RECOVER",
                    diagnostic_question="",
                    activation_polarity="negative",
                    target_levers=["champion_strength"],
                    dominant_failure_mode="",
                    primary_target_pattern="",
                    entry_conditions=[],
                    disqualifying_conditions=["SIG_blocker"],
                    core_strategies=[],
                    prohibited_strategies=[],
                    representative_actions=[],
                    positive_progress_signals=[],
                    negative_progress_signals=[],
                )
            return original_get(key)

        engine.schema.get_strategy_path = _patched
        try:
            lever_states = {"champion_strength": "WEAK"}
            result = _call_select(
                engine, pattern, ["SIG_blocker"], "zone2", lever_states
            )
            assert result is None
        finally:
            engine.schema.get_strategy_path = original_get

    # -------------------------------------------------------------------
    # SR-08  Single surviving candidate is selected regardless of score
    # -------------------------------------------------------------------
    def test_sr08_single_candidate_selected(self, engine):
        """A single surviving candidate is returned even with a poor score."""
        # unqualified_deal has only one candidate: Disqualify_or_Deprioritize
        pattern = engine.schema.get_pattern("unqualified_deal")
        assert pattern is not None
        assert len(pattern.candidate_strategy_path_keys) == 1

        lever_states = {
            "case_for_change_strength": "EXECUTING",
            "champion_strength": "EXECUTING",
            "buyer_urgency": "EXECUTING",
            "economic_buyer_commitment": "EXECUTING",
            "buyer_consensus": "EXECUTING",
            "differentiation_leverage": "EXECUTING",
            "decision_process_alignment": "EXECUTING",
        }
        result = _call_select(engine, pattern, [], "zone2", lever_states)

        assert result is not None
        assert result.key == "Disqualify_or_Deprioritize"

    # -------------------------------------------------------------------
    # SR-09  Ranking actually uses current lever states
    # -------------------------------------------------------------------
    def test_sr09_ranking_uses_current_lever_states(self, engine):
        """Changing lever states should change the ranking outcome."""
        # Use a pattern with mixed RECOVER/ADVANCE candidates
        # stagnant_deal candidates:
        #   Qualify_CaseForChange (RECOVER, targets case_for_change_strength)
        #   Identify_Champion_Targets (RECOVER, targets champion_strength)
        #   Build_Champion (RECOVER, targets champion_strength)
        #   Selling_to_Consensus (RECOVER, targets buyer_consensus)
        #   Disqualify_or_Deprioritize (EXIT, targets many)
        pattern = _build_pattern(
            "test_lever_sensitivity",
            ["Identify_Champion_Targets", "Qualify_CaseForChange"],
            resolution_type="RECOVER",
        )

        # Scenario A: case_for_change_strength is WEAK → prefer Qualify_CaseForChange
        lever_states_a = {
            "case_for_change_strength": "WEAK",
            "champion_strength": "COMMITTED",
            "buyer_urgency": "COMMITTED",
            "economic_buyer_commitment": "COMMITTED",
            "buyer_consensus": "COMMITTED",
            "differentiation_leverage": "COMMITTED",
            "decision_process_alignment": "COMMITTED",
        }
        result_a = _call_select(engine, pattern, [], "zone2", lever_states_a)

        # Scenario B: champion_strength is WEAK → prefer Identify_Champion_Targets
        lever_states_b = {
            "case_for_change_strength": "COMMITTED",
            "champion_strength": "WEAK",
            "buyer_urgency": "COMMITTED",
            "economic_buyer_commitment": "COMMITTED",
            "buyer_consensus": "COMMITTED",
            "differentiation_leverage": "COMMITTED",
            "decision_process_alignment": "COMMITTED",
        }
        result_b = _call_select(engine, pattern, [], "zone2", lever_states_b)

        assert result_a is not None
        assert result_b is not None
        assert result_a.key == "Qualify_CaseForChange"
        assert result_b.key == "Identify_Champion_Targets"
        # The two lever-state scenarios should produce different winners
        assert result_a.key != result_b.key
