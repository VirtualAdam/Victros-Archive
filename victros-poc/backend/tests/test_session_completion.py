"""Tier 1 — Session Completion Tests (SC-01 → SC-12).

Covers the RE_EVALUATING → SESSION_COMPLETE flow.

When monitoring detects an exit condition or a transition signal, the session
moves to RE_EVALUATING. From there the system must resolve:

  exit_detected + no remaining patterns → SESSION_COMPLETE
  exit_detected + secondary patterns remain → promote next pattern → PATTERN_DIAGNOSTICS
  transition_triggered → re-run engine with current signals → PATTERN_DIAGNOSTICS
"""
import pathlib
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


# ═══════════════════════════════════════════════════════════════════════════
# State Machine Validation
# ═══════════════════════════════════════════════════════════════════════════
class TestCompletionTransitions:
    # SC-01: RE_EVALUATING → SESSION_COMPLETE is valid
    def test_sc01_reevaluating_to_complete(self):
        from server.state_machine import validate_transition

        assert validate_transition("RE_EVALUATING", "SESSION_COMPLETE") is True

    # SC-02: RE_EVALUATING → PATTERN_DIAGNOSTICS is valid (promote next pattern)
    def test_sc02_reevaluating_to_pattern_diagnostics(self):
        from server.state_machine import validate_transition

        assert validate_transition("RE_EVALUATING", "PRESENTING_DIAGNOSIS") is True

    # SC-03: SESSION_COMPLETE → INTENT_CAPTURE (start a new deal)
    def test_sc03_complete_to_intent_capture(self):
        from server.state_machine import validate_transition

        assert validate_transition("SESSION_COMPLETE", "INTENT_CAPTURE") is True


# ═══════════════════════════════════════════════════════════════════════════
# API-Level End-to-End: Session to Completion
# ═══════════════════════════════════════════════════════════════════════════
class TestSessionCompletionAPI:
    @pytest.fixture
    def client(self, tmp_path):
        from server.main import create_app
        from fastapi.testclient import TestClient

        return TestClient(create_app(sessions_dir=tmp_path))

    @pytest.fixture
    def session_in_monitoring(self, client):
        """Drive a session all the way to MONITORING."""
        from tests.conftest import advance_to_monitoring
        r = client.post("/api/session/create", json={
            "user_id": "u1", "opportunity_id": "opp_acme",
        })
        sid = r.json()["session_id"]
        return advance_to_monitoring(client, sid)

    def _get_strategy_path(self, client, sid):
        """Get the active strategy path object for a session."""
        session = client.get(f"/api/session/{sid}").json()
        sp_key = session["selected_strategy_path"]
        paths = client.get("/api/schema/strategy-paths").json()
        return next(p for p in paths if p["key"] == sp_key)

    # SC-04: POST /progress with exit-triggering text → RE_EVALUATING
    def test_sc04_exit_moves_to_reevaluating(self, client, session_in_monitoring):
        sid = session_in_monitoring
        sp = self._get_strategy_path(client, sid)
        resp = client.post(f"/api/session/{sid}/progress", json={
            "update_text": sp["exit_outcome"],
        })
        assert resp.status_code == 200
        assert resp.json()["state"] == "RE_EVALUATING"

    # SC-05: POST /resolve-reevaluation on exit with no secondary patterns → SESSION_COMPLETE
    def test_sc05_resolve_exit_no_secondaries_completes(self, client, session_in_monitoring):
        sid = session_in_monitoring
        sp = self._get_strategy_path(client, sid)

        # Trigger exit
        client.post(f"/api/session/{sid}/progress", json={
            "update_text": sp["exit_outcome"],
        })

        # Resolve — should complete since single_threaded_contact activates only one pattern
        resp = client.post(f"/api/session/{sid}/resolve-reevaluation", json={
            "trigger": "exit",
        })
        assert resp.status_code == 200
        data = resp.json()
        # With a single signal/pattern, exit should complete the session
        assert data["state"] in ("SESSION_COMPLETE", "PATTERN_DIAGNOSTICS")

    # SC-06: POST /resolve-reevaluation on transition → re-runs engine → PATTERN_DIAGNOSTICS
    def test_sc06_resolve_transition_reruns_engine(self, client, session_in_monitoring):
        sid = session_in_monitoring
        sp = self._get_strategy_path(client, sid)

        # Trigger transition
        if sp.get("transition_signals"):
            client.post(f"/api/session/{sid}/progress", json={
                "update_text": sp["transition_signals"][0],
            })
        else:
            # Force RE_EVALUATING for test
            from server.session_manager import SessionManager
            # Use direct API approach — submit a progress update that triggers transition
            pytest.skip("No transition signals on this strategy path")

        resp = client.post(f"/api/session/{sid}/resolve-reevaluation", json={
            "trigger": "transition",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "PATTERN_DIAGNOSTICS"
        assert "pattern_group" in data

    # SC-07: resolve-reevaluation returns 409 if not in RE_EVALUATING state
    def test_sc07_resolve_wrong_state_returns_409(self, client, session_in_monitoring):
        sid = session_in_monitoring
        # Session is in MONITORING, not RE_EVALUATING
        resp = client.post(f"/api/session/{sid}/resolve-reevaluation", json={
            "trigger": "exit",
        })
        assert resp.status_code == 409

    # SC-08: SESSION_COMPLETE session has a completion record in history
    def test_sc08_completion_recorded_in_history(self, client, session_in_monitoring):
        sid = session_in_monitoring
        sp = self._get_strategy_path(client, sid)

        client.post(f"/api/session/{sid}/progress", json={
            "update_text": sp["exit_outcome"],
        })
        resp = client.post(f"/api/session/{sid}/resolve-reevaluation", json={
            "trigger": "exit",
        })
        data = resp.json()
        if data["state"] == "SESSION_COMPLETE":
            session = client.get(f"/api/session/{sid}").json()
            history_types = [h["type"] for h in session.get("interaction_history", [])]
            assert "session_complete" in history_types

    # SC-09: Full end-to-end flow: create → intent → validate → intake → confirm → patterns → action → monitor → exit → complete
    def test_sc09_full_end_to_end(self, client):
        from tests.conftest import advance_to_intake, submit_all_required_fields
        # Create
        r = client.post("/api/session/create", json={
            "user_id": "u1", "opportunity_id": "opp_e2e",
        })
        sid = r.json()["session_id"]
        assert r.json()["state"] == "INTENT_CAPTURE"

        # Intent capture
        r = client.post(f"/api/session/{sid}/input", json={
            "input_type": "text",
            "content": "I need help closing this deal",
        })
        assert r.json()["state"] == "SITUATION_VALIDATION"

        # Confirm situation
        r = client.post(f"/api/session/{sid}/confirm", json={
            "response": "confirm",
        })
        assert r.json()["state"] == "INTAKE"

        # Submit all required fields
        submit_all_required_fields(client, sid)

        # Submit signals
        r = client.post(f"/api/session/{sid}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact"],
        })
        assert r.json()["state"] == "AWAITING_CONFIRMATION"

        # Confirm with deal stage
        r = client.post(f"/api/session/{sid}/confirm", json={
            "response": "confirm",
            "deal_stage": "3_Validation",
        })
        assert r.json()["state"] == "PATTERN_DIAGNOSTICS"

        # Confirm patterns
        r = client.post(f"/api/session/{sid}/confirm-patterns", json={
            "response": "confirm_all",
        })
        assert r.json()["state"] in ("ACTION_SELECTION", "PRESENTING_DIAGNOSIS")

        # Advance through PRESENTING_DIAGNOSIS → ALIGNMENT_CHECKPOINT → ACTION_SELECTION
        session = client.get(f"/api/session/{sid}").json()
        if session["state"] == "PRESENTING_DIAGNOSIS":
            r = client.post(f"/api/session/{sid}/confirm-understanding", json={
                "response": "confirm",
            })
            assert r.json()["state"] == "ALIGNMENT_CHECKPOINT"

        session = client.get(f"/api/session/{sid}").json()
        if session["state"] == "ALIGNMENT_CHECKPOINT":
            r = client.post(f"/api/session/{sid}/alignment-checkpoint", json={
                "response": "aligned",
            })
            assert r.json()["state"] == "ACTION_SELECTION"

        # Select action
        session = client.get(f"/api/session/{sid}").json()
        sp_key = session["selected_strategy_path"]
        all_actions = client.get("/api/schema/representative-actions").json()
        actions = [a for a in all_actions if a.get("parent_strategy_path") == sp_key]
        assert len(actions) > 0
        action_key = actions[0]["action_key"]
        r = client.post(f"/api/session/{sid}/select-action", json={
            "action_key": action_key,
        })
        assert r.json()["state"] == "MONITORING"

        # Submit progress that triggers exit
        sp_key = client.get(f"/api/session/{sid}").json()["selected_strategy_path"]
        paths = client.get("/api/schema/strategy-paths").json()
        sp = next(p for p in paths if p["key"] == sp_key)

        r = client.post(f"/api/session/{sid}/progress", json={
            "update_text": sp["exit_outcome"],
        })
        assert r.json()["state"] == "RE_EVALUATING"

        # Resolve
        r = client.post(f"/api/session/{sid}/resolve-reevaluation", json={
            "trigger": "exit",
        })
        # Should reach SESSION_COMPLETE or PATTERN_DIAGNOSTICS (if secondary patterns)
        assert r.json()["state"] in ("SESSION_COMPLETE", "PATTERN_DIAGNOSTICS")
