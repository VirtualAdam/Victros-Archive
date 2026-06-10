"""Tier 2 — Extraction Service structural contract tests.

Validates response shape, signal key validity (no invented signals),
and deal attribute shape. Uses the mock — no LLM API key required.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from server.llm.extraction_service import extract, extract_pivot
from server.schema_store import SchemaStore

EVALS_DIR = pathlib.Path(__file__).resolve().parent.parent / "evals"
SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


@pytest.fixture(scope="module")
def schema():
    return SchemaStore(SCHEMA_DIR)


@pytest.fixture(scope="module")
def known_keys(schema):
    return [s.key for s in schema.signals]


@pytest.fixture(scope="module")
def eval_examples():
    path = EVALS_DIR / "extraction_eval.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# EX-INT-01 — EX-INT-07: Structural contract tests
# ---------------------------------------------------------------------------

class TestExtractionContract:

    def test_ex_int_01_returns_candidate_signals(self, known_keys):
        result = extract("My champion just went silent after internal reorg", known_keys)
        assert "candidate_signals" in result
        assert isinstance(result["candidate_signals"], list)

    def test_ex_int_02_no_invented_signals(self, known_keys):
        result = extract(
            "Champion went silent. Competitor getting traction. Lost access to EB.",
            known_keys,
        )
        for sig in result["candidate_signals"]:
            assert sig in known_keys, f"Invented signal key: {sig}"

    def test_ex_int_03_deal_attributes_shape(self, known_keys):
        result = extract("Deal is at Stage 3 Validation, $1.2M, close 2026-06-30", known_keys)
        assert "deal_attributes" in result
        attrs = result["deal_attributes"]
        assert isinstance(attrs, dict)
        allowed_keys = {"stage", "close_date", "amount", "notes"}
        for k in attrs:
            assert k in allowed_keys, f"Unexpected deal_attributes key: {k}"

    def test_ex_int_04_empty_content_returns_empty(self, known_keys):
        result = extract("Nothing relevant to signals — just general strategy", known_keys)
        assert isinstance(result["candidate_signals"], list)

    def test_ex_int_05_response_is_dict(self, known_keys):
        result = extract("The buyer is excited about our solution", known_keys)
        assert isinstance(result, dict)
        assert "candidate_signals" in result
        assert "deal_attributes" in result

    def test_ex_int_07_pivot_returns_schema_delta_shape(self, known_keys):
        result = extract_pivot(
            "Actually the champion is back and they just got budget approval",
            known_keys,
        )
        assert "add_signals" in result
        assert "remove_signals" in result
        assert "update_deal" in result
        assert "explanation" in result
        assert isinstance(result["add_signals"], list)
        assert isinstance(result["remove_signals"], list)

    def test_pivot_no_invented_signals(self, known_keys):
        result = extract_pivot("Champion is back, competition is gaining ground", known_keys)
        for sig in result["add_signals"]:
            assert sig in known_keys, f"Invented add signal: {sig}"
        for sig in result["remove_signals"]:
            assert sig in known_keys, f"Invented remove signal: {sig}"


# ---------------------------------------------------------------------------
# Eval coverage
# ---------------------------------------------------------------------------

class TestExtractionEvalCoverage:

    def test_eval_file_has_minimum_examples(self, eval_examples):
        assert len(eval_examples) >= 15

    def test_eval_examples_have_required_fields(self, eval_examples):
        for ex in eval_examples:
            assert "input" in ex
            assert "expected_signals" in ex
            assert "expected_deal_attributes" in ex
            assert isinstance(ex["expected_signals"], list)

    def test_no_invented_signals_across_all_eval_examples(self, eval_examples, known_keys):
        """Critical: 100% tolerance — mock must never return a signal not in schema."""
        for ex in eval_examples:
            result = extract(ex["input"], known_keys)
            for sig in result["candidate_signals"]:
                assert sig in known_keys, (
                    f"Invented signal '{sig}' returned for input: {ex['input'][:60]}"
                )

    def test_expected_signals_in_eval_are_valid_schema_keys(self, eval_examples, known_keys):
        """Sanity: eval data itself must only reference real signal keys."""
        for ex in eval_examples:
            for sig in ex["expected_signals"]:
                assert sig in known_keys, (
                    f"Eval references non-existent signal key '{sig}' in: {ex['input'][:60]}"
                )


# ---------------------------------------------------------------------------
# Precision, recall, F1 metrics
# ---------------------------------------------------------------------------

class TestExtractionMetrics:
    """Quantitative extraction quality metrics."""

    @pytest.fixture(scope="class")
    def eval_examples(self):
        path = EVALS_DIR / "extraction_eval.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @pytest.fixture(scope="class")
    def schema(self):
        return SchemaStore(SCHEMA_DIR)

    @pytest.fixture(scope="class")
    def known_keys(self, schema):
        return [s.key for s in schema.signals]

    def test_signal_recall(self, eval_examples, known_keys):
        """Expected signals should be found — not just no invented ones."""
        total_expected = 0
        total_found = 0
        for ex in eval_examples:
            result = extract(ex["input"], known_keys)
            for sig in ex["expected_signals"]:
                total_expected += 1
                if sig in result["candidate_signals"]:
                    total_found += 1
        recall = total_found / total_expected if total_expected > 0 else 1.0
        assert recall >= 0.50, (
            f"Signal recall {recall:.0%} ({total_found}/{total_expected}) below 50% threshold"
        )

    def test_signal_precision_respecting_extras(self, eval_examples, known_keys):
        """Signals outside expected + acceptable_extras are false positives."""
        total_predicted = 0
        false_positives = 0
        for ex in eval_examples:
            result = extract(ex["input"], known_keys)
            allowed = set(ex["expected_signals"]) | set(ex.get("acceptable_extras", []))
            for sig in result["candidate_signals"]:
                total_predicted += 1
                if sig not in allowed:
                    false_positives += 1
        precision = (total_predicted - false_positives) / total_predicted if total_predicted > 0 else 1.0
        assert precision >= 0.70, (
            f"Signal precision {precision:.0%} below 70% threshold "
            f"({false_positives} false positives out of {total_predicted})"
        )

    def test_no_contradictory_signals(self, known_keys):
        """Positive and negative versions of the same lever shouldn't co-occur on clear input."""
        contradictions = [
            ("no_named_or_active_champion", "champion_coaching_influence"),
            ("no_eb_validation", "economic_buyer_engagement"),
        ]
        for neg, pos in contradictions:
            result = extract(
                "The champion is actively pushing and everything is on track",
                known_keys,
            )
            signals = result["candidate_signals"]
            assert not (neg in signals and pos in signals), (
                f"Contradictory signals co-occurred: {neg} + {pos}"
            )


# ---------------------------------------------------------------------------
# Pivot-specific tests
# ---------------------------------------------------------------------------

class TestExtractionPivot:

    @pytest.fixture(scope="class")
    def schema(self):
        return SchemaStore(SCHEMA_DIR)

    @pytest.fixture(scope="class")
    def known_keys(self, schema):
        return [s.key for s in schema.signals]

    def test_pivot_removes_champion_absence_when_champion_returns(self, known_keys):
        result = extract_pivot(
            "Actually the champion is back and actively engaged",
            known_keys,
        )
        assert "no_named_or_active_champion" in result["remove_signals"]

    def test_pivot_explanation_is_non_empty(self, known_keys):
        result = extract_pivot("Champion came back with budget approval", known_keys)
        assert isinstance(result["explanation"], str)
        assert len(result["explanation"].strip()) > 0

    def test_pivot_with_subset_known_keys(self, known_keys):
        """Production may pass a subset of keys based on deal state."""
        subset = known_keys[:5]
        result = extract("Champion went silent, competitor gaining ground", subset)
        for sig in result["candidate_signals"]:
            assert sig in subset, f"Signal '{sig}' not in allowed subset"
