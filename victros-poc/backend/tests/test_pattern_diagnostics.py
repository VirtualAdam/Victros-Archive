"""Tier 1 — Pattern Diagnostics Layer Tests (PD-01 → PD-17).

These tests cover the missing Layer 3 from the system-flow spec:
  After EVALUATING, the engine activates a set of patterns but the user
  must confirm them before a strategy path is selected.

Written BEFORE pattern_diagnostics.py and the PATTERN_DIAGNOSTICS state exist.
The state machine must gain a new state and transitions:
  EVALUATING → PATTERN_DIAGNOSTICS
  PATTERN_DIAGNOSTICS → ACTION_SELECTION   (single confirmed pattern)
  PATTERN_DIAGNOSTICS → DUAL_PATTERN_TRADEOFF  (two+ confirmed patterns)
  PATTERN_DIAGNOSTICS → INTAKE  (user disagrees with all patterns)
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


@pytest.fixture
def schema_store():
    from server.schema_store import SchemaStore

    return SchemaStore(SCHEMA_DIR)


# ═══════════════════════════════════════════════════════════════════════════
# State Machine Transitions Through PATTERN_DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════
class TestPatternDiagnosticsTransitions:
    # PD-01: EVALUATING → PATTERN_DIAGNOSTICS is a valid transition
    def test_pd01_evaluating_to_pattern_diagnostics(self):
        from server.state_machine import validate_transition

        assert validate_transition("EVALUATING", "PATTERN_DIAGNOSTICS") is True

    # PD-02: PATTERN_DIAGNOSTICS → PRESENTING_DIAGNOSIS (confirmed patterns)
    def test_pd02_pattern_diagnostics_to_presenting_diagnosis(self):
        from server.state_machine import validate_transition

        assert validate_transition("PATTERN_DIAGNOSTICS", "PRESENTING_DIAGNOSIS") is True

    # PD-03: PATTERN_DIAGNOSTICS → INTAKE (user disagrees)
    def test_pd03_pattern_diagnostics_to_intake(self):
        from server.state_machine import validate_transition

        assert validate_transition("PATTERN_DIAGNOSTICS", "INTAKE") is True

    # PD-04: PATTERN_DIAGNOSTICS → INTAKE (user disagrees with all patterns)
    def test_pd04_pattern_diagnostics_to_intake(self):
        from server.state_machine import validate_transition

        assert validate_transition("PATTERN_DIAGNOSTICS", "INTAKE") is True

    # PD-05: PRESENTING_DIAGNOSIS is no longer directly reachable from EVALUATING
    # (The old shortcut is gone; EVALUATING must go through PATTERN_DIAGNOSTICS first)
    def test_pd05_evaluating_no_longer_skips_to_presenting(self):
        from server.state_machine import validate_transition

        assert validate_transition("EVALUATING", "PRESENTING_DIAGNOSIS") is False


# ═══════════════════════════════════════════════════════════════════════════
# Pattern Group Presentation Format
# ═══════════════════════════════════════════════════════════════════════════
class TestPatternGroupPresentation:
    # PD-06: format_pattern_group returns a list of pattern summaries
    def test_pd06_format_group_returns_summaries(self, schema_store):
        from server.pattern_diagnostics import format_pattern_group

        patterns = schema_store.get_patterns_by_keys(["singlethreaded_risk"])
        group = format_pattern_group(patterns)

        assert "patterns" in group
        assert len(group["patterns"]) == 1
        assert "summary" in group["patterns"][0]

    # PD-07: format_pattern_group includes diagnostic_questions for each pattern
    def test_pd07_format_group_includes_diagnostic_questions(self, schema_store):
        from server.pattern_diagnostics import format_pattern_group

        patterns = schema_store.get_patterns_by_keys(["singlethreaded_risk"])
        group = format_pattern_group(patterns)

        item = group["patterns"][0]
        assert "diagnostic_questions" in item
        assert len(item["diagnostic_questions"]) > 0

    # PD-08: format_pattern_group includes resolution_type for each pattern
    def test_pd08_format_group_includes_resolution_type(self, schema_store):
        from server.pattern_diagnostics import format_pattern_group

        patterns = schema_store.get_patterns_by_keys(["singlethreaded_risk"])
        group = format_pattern_group(patterns)

        item = group["patterns"][0]
        assert "resolution_type" in item
        assert item["resolution_type"] in ("RECOVER", "ADVANCE", "EXIT")

    # PD-09: format_pattern_group with multiple patterns includes a meta_explanation
    def test_pd09_multi_pattern_includes_meta_explanation(self, schema_store):
        from server.pattern_diagnostics import format_pattern_group

        patterns = schema_store.get_patterns_by_keys([
            "singlethreaded_risk",
            "stagnant_deal",
        ])
        group = format_pattern_group(patterns)

        assert "meta_explanation" in group
        assert len(group["meta_explanation"]) > 0

    # PD-10: format_pattern_group includes confirm/reject options
    def test_pd10_group_includes_confirmation_options(self, schema_store):
        from server.pattern_diagnostics import format_pattern_group

        patterns = schema_store.get_patterns_by_keys(["singlethreaded_risk"])
        group = format_pattern_group(patterns)

        assert "options" in group
        assert "confirm_all" in group["options"]
        assert "reject_all" in group["options"]


# ═══════════════════════════════════════════════════════════════════════════
# Pattern Confirmation Processing
# ═══════════════════════════════════════════════════════════════════════════
class TestPatternConfirmation:
    # PD-11: User confirms all patterns → all remain active, routes to PRESENTING_DIAGNOSIS
    def test_pd11_confirm_all_single_pattern(self, schema_store):
        from server.pattern_diagnostics import process_pattern_confirmation

        activated = schema_store.get_patterns_by_keys(["singlethreaded_risk"])
        result = process_pattern_confirmation(
            activated_patterns=activated,
            response="confirm_all",
        )

        assert result["confirmed_patterns"] == ["singlethreaded_risk"]
        assert result["next_state"] == "PRESENTING_DIAGNOSIS"

    # PD-12: Confirming two patterns also routes to PRESENTING_DIAGNOSIS
    def test_pd12_confirm_two_patterns_routes_to_presenting(self, schema_store):
        from server.pattern_diagnostics import process_pattern_confirmation

        activated = schema_store.get_patterns_by_keys([
            "singlethreaded_risk",
            "stagnant_deal",
        ])
        result = process_pattern_confirmation(
            activated_patterns=activated,
            response="confirm_all",
        )

        assert set(result["confirmed_patterns"]) == {"singlethreaded_risk", "stagnant_deal"}
        assert result["next_state"] == "PRESENTING_DIAGNOSIS"

    # PD-13: User rejects all patterns → next_state is INTAKE
    def test_pd13_reject_all_routes_to_intake(self, schema_store):
        from server.pattern_diagnostics import process_pattern_confirmation

        activated = schema_store.get_patterns_by_keys(["singlethreaded_risk"])
        result = process_pattern_confirmation(
            activated_patterns=activated,
            response="reject_all",
        )

        assert result["confirmed_patterns"] == []
        assert result["next_state"] == "INTAKE"

    # PD-14: confirm_subset is treated as confirm_all for backward compat
    def test_pd14_confirm_subset_treated_as_confirm_all(self, schema_store):
        from server.pattern_diagnostics import process_pattern_confirmation

        activated = schema_store.get_patterns_by_keys([
            "singlethreaded_risk",
            "stagnant_deal",
        ])
        result = process_pattern_confirmation(
            activated_patterns=activated,
            response="confirm_subset",
            confirmed_keys=["singlethreaded_risk"],
        )

        # confirm_subset is treated as confirm_all
        assert set(result["confirmed_patterns"]) == {"singlethreaded_risk", "stagnant_deal"}
        assert result["next_state"] == "PRESENTING_DIAGNOSIS"

    # PD-15: confirm_subset with empty keys is also treated as confirm_all
    def test_pd15_confirm_subset_empty_treated_as_confirm_all(self, schema_store):
        from server.pattern_diagnostics import process_pattern_confirmation

        activated = schema_store.get_patterns_by_keys(["singlethreaded_risk"])
        result = process_pattern_confirmation(
            activated_patterns=activated,
            response="confirm_subset",
            confirmed_keys=[],
        )

        # confirm_subset treated as confirm_all regardless of confirmed_keys
        assert result["confirmed_patterns"] == ["singlethreaded_risk"]
        assert result["next_state"] == "PRESENTING_DIAGNOSIS"


# ═══════════════════════════════════════════════════════════════════════════
# API-Level Pattern Diagnostics Flow
# ═══════════════════════════════════════════════════════════════════════════
class TestPatternDiagnosticsAPI:
    @pytest.fixture
    def client(self, tmp_path):
        from server.main import create_app
        from fastapi.testclient import TestClient

        return TestClient(create_app(sessions_dir=tmp_path))

    @pytest.fixture
    def session_in_pattern_diagnostics(self, client):
        """Drive a session from NEW_SESSION through to PATTERN_DIAGNOSTICS."""
        from tests.conftest import advance_to_pattern_diagnostics
        resp = client.post("/api/session/create", json={
            "user_id": "user_001",
            "opportunity_id": "opp_acme",
        })
        sid = resp.json()["session_id"]
        advance_to_pattern_diagnostics(client, sid)
        return sid

    # PD-16: After confirming signals, session reaches PATTERN_DIAGNOSTICS (not PRESENTING_DIAGNOSIS)
    def test_pd16_session_reaches_pattern_diagnostics(self, session_in_pattern_diagnostics, client):
        sid = session_in_pattern_diagnostics
        state = client.get(f"/api/session/{sid}").json()["state"]
        assert state == "PATTERN_DIAGNOSTICS"

    # PD-17: POST /api/session/{id}/confirm-patterns confirms and advances state
    def test_pd17_confirm_patterns_endpoint(self, session_in_pattern_diagnostics, client):
        sid = session_in_pattern_diagnostics
        resp = client.post(f"/api/session/{sid}/confirm-patterns", json={
            "response": "confirm_all",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "PRESENTING_DIAGNOSIS"
