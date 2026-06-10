"""Tier 2 — Intent Router structural contract tests.

These tests validate the service contract (response shape, valid values)
using the mock. No LLM API key required.

Tests are marked `llm` so they can be deselected in CI with -m 'not llm'
once the real LLM is wired in. Against the mock they always run.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from server.llm.intent_router import classify

EVALS_DIR = pathlib.Path(__file__).resolve().parent.parent / "evals"
VALID_CATEGORIES = {"strategic", "general"}


# ---------------------------------------------------------------------------
# IR-INT-01 — IR-INT-05: Structural contract tests
# ---------------------------------------------------------------------------

class TestIntentRouterContract:

    def test_ir_int_01_strategic_input_returns_strategic(self):
        result = classify("My champion just went silent")
        assert result["category"] == "strategic"

    def test_ir_int_02_general_input_returns_general(self):
        result = classify("Can you draft a follow-up email for me?")
        assert result["category"] == "general"

    def test_ir_int_03_response_is_valid_shape(self):
        result = classify("The deal stage just moved to validation")
        assert isinstance(result, dict)
        assert "category" in result
        assert result["category"] in VALID_CATEGORIES
        assert "confidence" in result
        assert isinstance(result["confidence"], float)

    def test_ir_int_05_empty_input_no_crash(self):
        result = classify("")
        assert isinstance(result, dict)
        assert result["category"] in VALID_CATEGORIES

    def test_ir_whitespace_input_no_crash(self):
        result = classify("   ")
        assert result["category"] in VALID_CATEGORIES


# ---------------------------------------------------------------------------
# Eval coverage: assert mock passes the labeled eval set
# ---------------------------------------------------------------------------

class TestIntentRouterEvalCoverage:

    @pytest.fixture(scope="class")
    def eval_examples(self):
        path = EVALS_DIR / "intent_router_eval.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_eval_file_has_minimum_examples(self, eval_examples):
        assert len(eval_examples) >= 20

    def test_eval_examples_have_required_fields(self, eval_examples):
        for ex in eval_examples:
            assert "input" in ex
            assert "expected_category" in ex
            assert ex["expected_category"] in VALID_CATEGORIES

    def test_mock_accuracy_on_eval_set(self, eval_examples):
        """Strategic recall constraint — 100% for mock, 90% for LLM."""
        from server.llm.client import is_mock_mode
        strategic_examples = [e for e in eval_examples if e["expected_category"] == "strategic"]
        correct_strategic = sum(
            1 for e in strategic_examples if classify(e["input"])["category"] == "strategic"
        )
        if is_mock_mode():
            threshold = len(strategic_examples)
            label = "Mock"
        else:
            threshold = int(len(strategic_examples) * 0.90)
            label = "LLM"
        assert correct_strategic >= threshold, (
            f"{label} missed {len(strategic_examples) - correct_strategic} strategic examples "
            f"({correct_strategic}/{len(strategic_examples)}, threshold={threshold})"
        )

    def test_no_invented_categories(self, eval_examples):
        for ex in eval_examples:
            result = classify(ex["input"])
            assert result["category"] in VALID_CATEGORIES, (
                f"Unexpected category '{result['category']}' for input: {ex['input'][:60]}"
            )


# ---------------------------------------------------------------------------
# Precision, recall, F1 metrics
# ---------------------------------------------------------------------------

class TestIntentRouterMetrics:
    """Quantitative classification metrics beyond binary pass/fail."""

    @pytest.fixture(scope="class")
    def eval_examples(self):
        path = EVALS_DIR / "intent_router_eval.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _confusion_matrix(self, eval_examples):
        tp = fp = fn = tn = 0
        for ex in eval_examples:
            predicted = classify(ex["input"])["category"]
            expected = ex["expected_category"]
            if predicted == "strategic" and expected == "strategic":
                tp += 1
            elif predicted == "strategic" and expected == "general":
                fp += 1
            elif predicted == "general" and expected == "strategic":
                fn += 1
            else:
                tn += 1
        return tp, fp, fn, tn

    def test_f1_score_above_threshold(self, eval_examples):
        """Aggregate F1 must be above 0.80."""
        tp, fp, fn, tn = self._confusion_matrix(eval_examples)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        assert f1 >= 0.80, (
            f"F1={f1:.3f} below 0.80 (P={precision:.3f}, R={recall:.3f}, "
            f"TP={tp}, FP={fp}, FN={fn}, TN={tn})"
        )

    def test_general_precision(self, eval_examples):
        """General inputs should not all be classified as strategic."""
        general_examples = [e for e in eval_examples if e["expected_category"] == "general"]
        correct_general = sum(
            1 for e in general_examples if classify(e["input"])["category"] == "general"
        )
        precision = correct_general / len(general_examples) if general_examples else 1.0
        assert precision >= 0.60, (
            f"General precision too low: {precision:.0%} "
            f"({len(general_examples) - correct_general}/{len(general_examples)} false positives)"
        )

    def test_confidence_is_between_0_and_1(self, eval_examples):
        """Confidence must be a valid probability."""
        for ex in eval_examples:
            result = classify(ex["input"])
            assert 0.0 <= result["confidence"] <= 1.0, (
                f"Confidence {result['confidence']} out of range for: {ex['input'][:60]}"
            )


# ---------------------------------------------------------------------------
# Robustness tests
# ---------------------------------------------------------------------------

class TestIntentRouterRobustness:

    def test_long_input_no_crash(self):
        """Should handle very long inputs without crashing."""
        long_input = "My champion went silent. " * 200
        result = classify(long_input)
        assert result["category"] in VALID_CATEGORIES

    def test_deterministic_on_same_input(self):
        """Same input should produce same category."""
        input_text = "The deal stage just moved to validation"
        results = [classify(input_text)["category"] for _ in range(5)]
        assert len(set(results)) == 1, f"Non-deterministic results: {results}"
