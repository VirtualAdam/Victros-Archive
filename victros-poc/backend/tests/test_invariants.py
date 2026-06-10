"""Property-based invariant tests for the Victros Decision Engine.

These tests assert that structural rules hold for ANY combination of signals.
They do not encode specific expected outputs — only universal invariants.

Test generation strategy:
  - Every individual signal (23 tests)
  - Every pair of signals (C(23,2) = 253 tests)
  - A sample of 50 random triplets
  - All signals at once (1 test)
  - Empty set (1 test)

For each signal set, ALL invariants are asserted.
"""
from __future__ import annotations

import itertools
import pathlib
import random

import pytest

from server.decision_engine import (
    DecisionEngine,
    LEVER_ORDER,
    SEVERITY_WEIGHT,
    STRUCTURAL_BONUS,
    STRUCTURAL_TYPES,
    density_factor,
)
from server.schema_store import SchemaStore

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"

schema_store = SchemaStore(SCHEMA_DIR)
engine = DecisionEngine(schema_store)

ALL_SIGNAL_KEYS = [s.key for s in schema_store.signals]
DEFAULT_STAGE = "3_Validation"

# ---------------------------------------------------------------------------
# Generate signal sets
# ---------------------------------------------------------------------------
_single = [[k] for k in ALL_SIGNAL_KEYS]
_pairs = [list(c) for c in itertools.combinations(ALL_SIGNAL_KEYS, 2)]

random.seed(42)
_all_triples = list(itertools.combinations(ALL_SIGNAL_KEYS, 3))
_triples = [list(c) for c in random.sample(_all_triples, min(50, len(_all_triples)))]

_all_signals = [list(ALL_SIGNAL_KEYS)]
_empty = [[]]

ALL_SIGNAL_SETS: list[list[str]] = _single + _pairs + _triples + _all_signals + _empty


def _signal_set_id(signals: list[str]) -> str:
    """Human-readable pytest ID for a signal set."""
    if not signals:
        return "EMPTY"
    if len(signals) <= 3:
        return "+".join(signals)
    return f"{len(signals)}_signals"


# ---------------------------------------------------------------------------
# Lever state ordering helper
# ---------------------------------------------------------------------------
LEVER_STATE_RANK = {"WEAK": 0, "CONNECTED": 1, "COMMITTED": 2, "EXECUTING": 3}


# ---------------------------------------------------------------------------
# INV-01: Single Priority Pattern
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv01_single_priority_pattern(signals: list[str]):
    """If activated patterns exist and pass sufficiency, exactly one primary_pattern."""
    result = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    if result.primary_pattern is not None:
        assert isinstance(result.primary_pattern, str)
        assert len(result.primary_pattern) > 0
    # When primary_pattern is None, that's acceptable (no patterns activated or
    # none passed sufficiency). But it must never be a list or multiple values.


# ---------------------------------------------------------------------------
# INV-02: Strategy Path From Candidate Set
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv02_strategy_path_from_candidates(signals: list[str]):
    """Selected strategy_path must be in the primary pattern's candidate list."""
    result = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    if result.strategy_path is None:
        return
    assert result.primary_pattern is not None
    pattern = schema_store.get_pattern(result.primary_pattern)
    assert pattern is not None, f"Primary pattern {result.primary_pattern} not in schema"
    assert result.strategy_path in pattern.candidate_strategy_path_keys, (
        f"Strategy path {result.strategy_path} not in candidates "
        f"{pattern.candidate_strategy_path_keys} for pattern {result.primary_pattern}"
    )


# ---------------------------------------------------------------------------
# INV-03: PatternWeight Ordering
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv03_pattern_weight_ordering(signals: list[str]):
    """Primary pattern must have PatternWeight >= all secondary patterns."""
    result = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    if result.primary_pattern is None or not result.secondary_patterns:
        return

    signal_objects = engine._resolve_signals(signals)
    all_pattern_keys = [result.primary_pattern] + result.secondary_patterns
    all_patterns = [schema_store.get_pattern(k) for k in all_pattern_keys]
    all_patterns = [p for p in all_patterns if p is not None]

    lever_states = engine.evaluate_signals(signals)
    weights = engine.compute_pattern_weights(all_patterns, signal_objects, lever_states)

    primary_weight = weights.get(result.primary_pattern, 0.0)
    # The primary is selected from sufficiency-passing patterns only,
    # so we compare against all activated patterns' weights.
    # Primary must have highest weight among sufficient patterns.
    sufficient_patterns = [
        p for p in all_patterns if engine.sufficient_authority(p, signal_objects)
    ]
    for p in sufficient_patterns:
        if p.key != result.primary_pattern:
            assert primary_weight >= weights.get(p.key, 0.0), (
                f"Primary {result.primary_pattern} (weight={primary_weight}) "
                f"< secondary {p.key} (weight={weights.get(p.key, 0.0)})"
            )


# ---------------------------------------------------------------------------
# INV-04: Signal Subset Monotonicity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals",
    [s for s in ALL_SIGNAL_SETS if len(s) >= 2],
    ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS if len(s) >= 2],
)
def test_inv04_signal_subset_monotonicity(signals: list[str]):
    """Adding signals must never deactivate a pattern (OR-logic activation)."""
    # Take a proper subset: first signal only
    subset = [signals[0]]
    result_subset = engine.run(active_signals=subset, deal_stage=DEFAULT_STAGE)
    result_full = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)

    # Collect all activated pattern keys (primary + secondary) for each
    def activated_keys(r):
        keys = set()
        if r.primary_pattern:
            keys.add(r.primary_pattern)
        keys.update(r.secondary_patterns)
        return keys

    subset_activated = activated_keys(result_subset)
    full_activated = activated_keys(result_full)

    # Every pattern activated by the subset must also be activated by the superset.
    # Note: we check raw activation (signal-driven OR logic), not sufficiency-filtered output.
    subset_signal_objs = engine._resolve_signals(subset)
    full_signal_objs = engine._resolve_signals(signals)
    raw_subset = {p.key for p in engine.activate_patterns_from_signals(subset_signal_objs)}
    raw_full = {p.key for p in engine.activate_patterns_from_signals(full_signal_objs)}

    missing = raw_subset - raw_full
    assert not missing, (
        f"Patterns {missing} activated by subset {subset} "
        f"but not by superset {signals}"
    )


# ---------------------------------------------------------------------------
# INV-05: Lever State Monotonicity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals",
    [s for s in ALL_SIGNAL_SETS if len(s) >= 2],
    ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS if len(s) >= 2],
)
def test_inv05_lever_state_monotonicity(signals: list[str]):
    """Adding a positive signal must never decrease a lever state."""
    # Build up signals one at a time
    prev_levers = engine.evaluate_signals([])
    for i in range(1, len(signals) + 1):
        current = signals[:i]
        current_levers = engine.evaluate_signals(current)
        added_signal = schema_store.get_signal(signals[i - 1])
        if added_signal is not None and added_signal.polarity == "positive":
            for lever_key in LEVER_ORDER:
                prev_rank = LEVER_STATE_RANK.get(prev_levers.get(lever_key, "WEAK"), 0)
                curr_rank = LEVER_STATE_RANK.get(current_levers.get(lever_key, "WEAK"), 0)
                assert curr_rank >= prev_rank, (
                    f"Lever {lever_key} decreased from "
                    f"{prev_levers.get(lever_key)} to {current_levers.get(lever_key)} "
                    f"when adding positive signal {signals[i-1]}"
                )
        prev_levers = current_levers


# ---------------------------------------------------------------------------
# INV-06: No Invented Signals in Output
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv06_no_invented_signals(signals: list[str]):
    """active_signals in result must be exactly the input signal set."""
    result = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    assert result.active_signals == signals, (
        f"Output signals {result.active_signals} != input {signals}"
    )


# ---------------------------------------------------------------------------
# INV-07: Representative Actions Belong to Strategy Path
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv07_actions_belong_to_strategy_path(signals: list[str]):
    """Every action in the result must belong to the selected strategy path."""
    result = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    if result.strategy_path is None:
        assert result.representative_actions == []
        return
    sp = schema_store.get_strategy_path(result.strategy_path)
    assert sp is not None
    allowed_actions = set(sp.representative_actions)
    for action_key in result.representative_actions:
        assert action_key in allowed_actions, (
            f"Action {action_key} not in strategy path "
            f"{result.strategy_path} actions {allowed_actions}"
        )


# ---------------------------------------------------------------------------
# INV-08: Secondary Patterns Are Disjoint From Primary
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv08_secondary_disjoint_from_primary(signals: list[str]):
    """Primary pattern must not appear in secondary_patterns."""
    result = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    if result.primary_pattern is None:
        return
    assert result.primary_pattern not in result.secondary_patterns, (
        f"Primary pattern {result.primary_pattern} also in secondary_patterns"
    )


# ---------------------------------------------------------------------------
# INV-09: Structural Signals Override Momentum at Equal Severity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv09_structural_overrides_momentum_at_equal_severity(signals: list[str]):
    """At equal severity, structurally-backed patterns must outweigh momentum-only."""
    result = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    if result.primary_pattern is None or not result.secondary_patterns:
        return

    signal_objects = engine._resolve_signals(signals)
    all_keys = [result.primary_pattern] + result.secondary_patterns
    all_patterns = [p for p in (schema_store.get_pattern(k) for k in all_keys) if p]
    lever_states = engine.evaluate_signals(signals)
    weights = engine.compute_pattern_weights(all_patterns, signal_objects, lever_states)

    # Group by severity
    by_severity: dict[str, list] = {}
    for p in all_patterns:
        by_severity.setdefault(p.severity, []).append(p)

    for sev, patterns_in_tier in by_severity.items():
        if len(patterns_in_tier) < 2:
            continue
        # Separate structural-backed vs momentum-only.
        # Compare weights after removing density factor so that signal count
        # does not obscure the structural-vs-momentum comparison.
        for p in patterns_in_tier:
            p_contributing = [s for s in signal_objects if p.key in s.target_patterns]
            p_has_structural = any(s.type in STRUCTURAL_TYPES for s in p_contributing)
            if p_has_structural:
                p_base = weights.get(p.key, 0) - density_factor(len(p_contributing))
                for q in patterns_in_tier:
                    if q.key == p.key:
                        continue
                    q_contributing = [s for s in signal_objects if q.key in s.target_patterns]
                    q_has_structural = any(s.type in STRUCTURAL_TYPES for s in q_contributing)
                    if not q_has_structural and len(q_contributing) > 0:
                        q_base = weights.get(q.key, 0) - density_factor(len(q_contributing))
                        assert p_base >= q_base, (
                            f"Structural pattern {p.key} (base_w={p_base}) "
                            f"< momentum pattern {q.key} (base_w={q_base}) "
                            f"at same severity {sev} (density-normalized)"
                        )


# ---------------------------------------------------------------------------
# INV-10: Sufficiency Filter Consistency
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv10_sufficiency_filter(signals: list[str]):
    """A pattern failing sufficient_authority() must never be primary_pattern."""
    result = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    if result.primary_pattern is None:
        return

    signal_objects = engine._resolve_signals(signals)
    primary = schema_store.get_pattern(result.primary_pattern)
    assert primary is not None
    assert engine.sufficient_authority(primary, signal_objects), (
        f"Primary pattern {result.primary_pattern} fails sufficient_authority "
        f"but was selected anyway"
    )


# ---------------------------------------------------------------------------
# INV-11: Empty Signal Set Returns None
# ---------------------------------------------------------------------------
def test_inv11_empty_signal_set():
    """engine.run(active_signals=[], ...) must return primary_pattern=None."""
    result = engine.run(active_signals=[], deal_stage=DEFAULT_STAGE)
    assert result.primary_pattern is None, (
        f"Empty signals produced primary_pattern={result.primary_pattern}"
    )
    assert result.strategy_path is None, (
        f"Empty signals produced strategy_path={result.strategy_path}"
    )


# ---------------------------------------------------------------------------
# INV-12: Determinism
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "signals", ALL_SIGNAL_SETS, ids=[_signal_set_id(s) for s in ALL_SIGNAL_SETS]
)
def test_inv12_determinism(signals: list[str]):
    """Same inputs must always produce same outputs."""
    r1 = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    r2 = engine.run(active_signals=signals, deal_stage=DEFAULT_STAGE)
    assert r1 == r2, (
        f"Non-deterministic output for signals={signals}:\n"
        f"  Run 1: primary={r1.primary_pattern}, sp={r1.strategy_path}\n"
        f"  Run 2: primary={r2.primary_pattern}, sp={r2.strategy_path}"
    )
