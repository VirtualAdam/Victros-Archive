"""Tier 2 — General AI Assist structural contract tests.

Validates response shape, persona voice, and absence of signal-activation
or strategy-path language. Uses the mock — no LLM API key required.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from server.llm.general_assist import assist

EVALS_DIR = pathlib.Path(__file__).resolve().parent.parent / "evals"

# Phrases that would indicate the mock is contaminating schema state.
_SCHEMA_STATE_PHRASES = [
    "activate signal",
    "select strategy",
    "strategy_path",
    "signal_key",
    "candidate_signals",
]


@pytest.fixture(scope="module")
def eval_examples():
    path = EVALS_DIR / "general_ai_eval.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# GA-INT-01 — GA-INT-03: Structural contract tests
# ---------------------------------------------------------------------------

class TestGeneralAssistContract:

    def test_ga_int_01_returns_prose_response(self):
        result = assist("Draft a follow-up email after a demo")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_ga_int_02_no_schema_state_modification_language(self):
        result = assist("Help me prepare for a discovery call")
        lower = result.lower()
        for phrase in _SCHEMA_STATE_PHRASES:
            assert phrase not in lower, f"Schema state language found: '{phrase}'"

    def test_ga_int_03_uses_persona_voice(self):
        result = assist("What should I focus on in my QBR?")
        # Persona voice: must mention Victros or use observable coaching verbs.
        coaching_verbs = ["ask", "map", "align", "validate", "confirm", "request",
                          "identify", "Victros"]
        assert any(v.lower() in result.lower() for v in coaching_verbs), (
            "Response does not appear to use coaching/persona voice"
        )

    def test_empty_input_no_crash(self):
        result = assist("")
        assert isinstance(result, str)

    def test_returns_string_not_dict(self):
        result = assist("Summarize this text: something relevant")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Eval coverage
# ---------------------------------------------------------------------------

class TestGeneralAssistEvalCoverage:

    def test_eval_file_has_minimum_examples(self, eval_examples):
        assert len(eval_examples) >= 5

    def test_eval_examples_have_required_fields(self, eval_examples):
        for ex in eval_examples:
            assert "input" in ex
            assert "checks" in ex

    def test_all_examples_return_non_empty(self, eval_examples):
        for ex in eval_examples:
            result = assist(ex["input"])
            assert isinstance(result, str) and len(result.strip()) > 0, (
                f"Empty response for input: {ex['input'][:60]}"
            )

    def test_no_schema_state_language_in_any_response(self, eval_examples):
        for ex in eval_examples:
            result = assist(ex["input"])
            lower = result.lower()
            for phrase in _SCHEMA_STATE_PHRASES:
                assert phrase not in lower, (
                    f"Schema state phrase '{phrase}' in response for: {ex['input'][:60]}"
                )
