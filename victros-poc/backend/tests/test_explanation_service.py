"""Tier 2 — Explanation Service structural contract tests.

Validates persona voice, rendering order signals, schema name fidelity,
and absence of first-person opinion language. Uses the mock — no LLM required.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from server.llm.explanation_service import explain
from server.schema_store import SchemaStore

EVALS_DIR = pathlib.Path(__file__).resolve().parent.parent / "evals"
SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"

_PROHIBITED_PHRASES = ["I think", "I believe", "I feel", "In my opinion"]


@pytest.fixture(scope="module")
def eval_examples():
    path = EVALS_DIR / "explanation_eval.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# EXP-INT-01 — EXP-INT-09: Structural contract tests
# ---------------------------------------------------------------------------

class TestExplanationContract:

    def _make_result(self, **overrides):
        base = {
            "primary_pattern": "singlethreaded_risk",
            "secondary_patterns": [],
            "strategy_path": "Selling_to_Consensus",
            "representative_actions": ["map_the_full_consensus_group_with_the_champion_and", "engage_each_stakeholder_in_persona_specific_outcom"],
            "active_signals": ["single_threaded_contact"],
            "lever_states": {k: "WEAK" for k in [
                "case_for_change_strength", "champion_strength", "economic_buyer_commitment",
                "buyer_consensus", "decision_process_alignment", "differentiation_leverage", "buyer_urgency"
            ]},
            "zone": "zone_2_mid_stage",
        }
        base.update(overrides)
        return base

    @staticmethod
    def _key_mentioned(key: str, text: str) -> bool:
        """Check if a schema key appears in text — exact or humanized form."""
        lower = text.lower()
        if key.lower() in lower:
            return True
        # Humanize: underscores/hyphens → spaces, case-insensitive
        humanized = key.replace("_", " ").replace("-", " ").lower()
        return humanized in lower

    def test_exp_int_01_returns_non_empty_string(self):
        result = explain(self._make_result(), context="diagnosis")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_exp_int_02_mentions_primary_pattern(self):
        dr = self._make_result()
        result = explain(dr, context="diagnosis")
        assert self._key_mentioned(dr["primary_pattern"], result), (
            f"Primary pattern '{dr['primary_pattern']}' not found in explanation"
        )

    def test_exp_int_03_mentions_strategy_path(self):
        dr = self._make_result()
        result = explain(dr, context="diagnosis")
        assert self._key_mentioned(dr["strategy_path"], result), (
            f"Strategy path '{dr['strategy_path']}' not found in explanation"
        )

    def test_exp_int_04_no_first_person_opinion(self):
        dr = self._make_result()
        result = explain(dr, context="diagnosis")
        for phrase in _PROHIBITED_PHRASES:
            assert phrase not in result, f"Prohibited phrase found: '{phrase}'"

    def test_exp_int_05_rendering_order_signals_present(self):
        dr = self._make_result()
        result = explain(dr, context="diagnosis")
        # Structural implication must appear before recommendation language
        structural_idx = result.lower().find("structural")
        recommend_idx = result.lower().find("recommend")
        assert structural_idx != -1, "Missing structural implication language"
        assert recommend_idx == -1 or structural_idx < recommend_idx, (
            "Rendering order violated: recommendation appears before structural implication"
        )

    def test_exp_int_06_actions_listed_in_diagnosis(self):
        dr = self._make_result()
        result = explain(dr, context="diagnosis")
        for action in dr["representative_actions"]:
            assert self._key_mentioned(action, result), (
                f"Action '{action}' not found in explanation"
            )

    def test_exp_int_07_summary_context_no_crash(self):
        dr = self._make_result(primary_pattern=None, strategy_path=None, representative_actions=[])
        result = explain(dr, context="summary")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_exp_int_08_tradeoff_context_mentions_both_patterns(self):
        dr = self._make_result(secondary_patterns=["competitive_mindshare"])
        result = explain(dr, context="tradeoff")
        assert self._key_mentioned(dr["primary_pattern"], result), (
            f"Primary pattern not found in tradeoff"
        )
        assert self._key_mentioned("competitive_mindshare", result), (
            "Secondary pattern 'competitive_mindshare' not found in tradeoff"
        )

    def test_exp_int_08_tradeoff_mentions_focus_combine_sequence(self):
        dr = self._make_result(secondary_patterns=["competitive_displacement"])
        result = explain(dr, context="tradeoff")
        assert "Focus" in result or "focus" in result
        assert "Combine" in result or "combine" in result
        assert "Sequence" in result or "sequence" in result

    def test_exp_int_09_monitoring_context_offers_yes_no_partial(self):
        dr = self._make_result()
        result = explain(dr, context="monitoring")
        assert "Yes" in result or "yes" in result
        assert "No" in result or "no" in result
        assert "Partial" in result or "partial" in result

    def test_mentions_victros_identified(self):
        dr = self._make_result()
        result = explain(dr, context="diagnosis")
        assert "Victros" in result

    def test_null_pattern_returns_graceful_message(self):
        dr = self._make_result(primary_pattern=None, strategy_path=None)
        result = explain(dr, context="diagnosis")
        assert isinstance(result, str)
        assert len(result.strip()) > 0


# ---------------------------------------------------------------------------
# Eval coverage
# ---------------------------------------------------------------------------

class TestExplanationEvalCoverage:

    def test_eval_file_has_minimum_examples(self, eval_examples):
        assert len(eval_examples) >= 10

    def test_eval_examples_have_required_fields(self, eval_examples):
        for ex in eval_examples:
            assert "decision_result" in ex
            assert "context" in ex
            assert "checks" in ex

    def test_no_first_person_opinion_across_all_examples(self, eval_examples):
        """0% tolerance on persona violations."""
        for ex in eval_examples:
            result = explain(ex["decision_result"], context=ex["context"])
            for phrase in _PROHIBITED_PHRASES:
                assert phrase not in result, (
                    f"Persona violation '{phrase}' in context={ex['context']}"
                )

    def test_all_examples_return_non_empty_string(self, eval_examples):
        for ex in eval_examples:
            result = explain(ex["decision_result"], context=ex["context"])
            assert isinstance(result, str) and len(result.strip()) > 0, (
                f"Empty response for context={ex['context']}"
            )

    @staticmethod
    def _key_mentioned(key: str, text: str) -> bool:
        lower = text.lower()
        if key.lower() in lower:
            return True
        humanized = key.replace("_", " ").replace("-", " ").lower()
        return humanized in lower

    def test_primary_pattern_present_when_check_requires(self, eval_examples):
        for ex in eval_examples:
            if not ex["checks"].get("mentions_primary_pattern"):
                continue
            primary = ex["decision_result"].get("primary_pattern")
            if primary is None:
                continue
            result = explain(ex["decision_result"], context=ex["context"])
            assert self._key_mentioned(primary, result), (
                f"Primary pattern '{primary}' not found in {ex['context']} response"
            )

    def test_strategy_path_present_when_check_requires(self, eval_examples):
        for ex in eval_examples:
            if not ex["checks"].get("mentions_strategy_path"):
                continue
            strategy = ex["decision_result"].get("strategy_path")
            if strategy is None:
                continue
            result = explain(ex["decision_result"], context=ex["context"])
            assert self._key_mentioned(strategy, result), (
                f"Strategy path '{strategy}' not found in {ex['context']} response"
            )

    def test_victros_mentioned_when_check_requires(self, eval_examples):
        for ex in eval_examples:
            if not ex["checks"].get("mentions_victros_identified"):
                continue
            result = explain(ex["decision_result"], context=ex["context"])
            assert "Victros" in result, (
                f"'Victros' not found in context={ex['context']} response"
            )


# ---------------------------------------------------------------------------
# Schema grounding validation
# ---------------------------------------------------------------------------

class TestExplanationSchemaGrounding:
    """Verify that eval fixtures use canonical schema keys."""

    @pytest.fixture(scope="class")
    def schema(self):
        return SchemaStore(SCHEMA_DIR)

    @pytest.fixture(scope="class")
    def eval_examples(self):
        path = EVALS_DIR / "explanation_eval.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_primary_patterns_are_canonical(self, eval_examples, schema):
        pattern_keys = {p.key for p in schema.patterns}
        for ex in eval_examples:
            p = ex["decision_result"].get("primary_pattern")
            if p is not None:
                assert p in pattern_keys, (
                    f"Non-canonical primary_pattern '{p}' in eval. "
                    f"Valid keys: {sorted(pattern_keys)}"
                )

    def test_secondary_patterns_are_canonical(self, eval_examples, schema):
        pattern_keys = {p.key for p in schema.patterns}
        for ex in eval_examples:
            for sp in ex["decision_result"].get("secondary_patterns", []):
                assert sp in pattern_keys, (
                    f"Non-canonical secondary_pattern '{sp}' in eval"
                )

    def test_strategy_paths_are_canonical(self, eval_examples, schema):
        strategy_keys = {s.key for s in schema.strategy_paths}
        for ex in eval_examples:
            s = ex["decision_result"].get("strategy_path")
            if s is not None:
                assert s in strategy_keys, (
                    f"Non-canonical strategy_path '{s}' in eval. "
                    f"Valid keys: {sorted(strategy_keys)}"
                )

    def test_active_signals_are_canonical(self, eval_examples, schema):
        signal_keys = {s.key for s in schema.signals}
        for ex in eval_examples:
            for sig in ex["decision_result"].get("active_signals", []):
                assert sig in signal_keys, (
                    f"Non-canonical signal '{sig}' in eval"
                )
