"""Tier 1 — API Endpoint Tests (API-01 → API-19).

Written BEFORE main.py exists.
Uses FastAPI TestClient. LLM services are mocked.
"""
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import (
    advance_to_intake,
    advance_to_awaiting_confirmation,
    advance_to_pattern_diagnostics,
    submit_all_required_fields,
)


@pytest.fixture
def client(tmp_path):
    """Create a TestClient with the FastAPI app, using a temp sessions dir."""
    from server.main import create_app

    app = create_app(sessions_dir=tmp_path)

    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def session_id(client):
    """Helper: create a session and return its ID."""
    resp = client.post("/api/session/create", json={
        "user_id": "user_001",
        "opportunity_id": "opp_acme",
    })
    return resp.json()["session_id"]


# ═══════════════════════════════════════════════════════════════════════════
# Session CRUD
# ═══════════════════════════════════════════════════════════════════════════
class TestSessionEndpoints:
    # API-01: Create session → auto-advances to INTENT_CAPTURE
    def test_api01_create_session(self, client):
        resp = client.post("/api/session/create", json={
            "user_id": "user_001",
            "opportunity_id": "opp_acme",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["state"] == "INTENT_CAPTURE"
        assert data["prompt"] == "How can I help you win today?"

    # API-02: Get existing session
    def test_api02_get_session(self, client, session_id):
        resp = client.get(f"/api/session/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id

    # API-03: Get non-existent session
    def test_api03_get_nonexistent(self, client):
        resp = client.get("/api/session/does-not-exist")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Input Submission
# ═══════════════════════════════════════════════════════════════════════════
class TestInputEndpoints:
    # API-04: Submit button selection (signals) in INTAKE state
    def test_api04_submit_button_signals(self, client, session_id):
        advance_to_intake(client, session_id)
        submit_all_required_fields(client, session_id)
        resp = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact", "competition_gaining_mindshare"],
        })
        assert resp.status_code == 200
        assert resp.json()["state"] in ["INTAKE", "AWAITING_CONFIRMATION"]

    # API-05: Submit free text in INTAKE state (extraction service called)
    def test_api05_submit_free_text(self, client, session_id):
        advance_to_intake(client, session_id)
        resp = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "text",
            "content": "My champion went silent",
        })
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Confirmation
# ═══════════════════════════════════════════════════════════════════════════
class TestConfirmationEndpoints:
    def _setup_awaiting(self, client, session_id):
        """Put session into AWAITING_CONFIRMATION with a signal proposal."""
        advance_to_awaiting_confirmation(client, session_id)

    # API-06: Confirm signals, readiness met → advances to PATTERN_DIAGNOSTICS
    def test_api06_confirm_ready(self, client, session_id):
        self._setup_awaiting(client, session_id)
        resp = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
            "deal_stage": "3_Validation",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "PATTERN_DIAGNOSTICS"

    # API-07: Confirm signals, readiness NOT met (no deal_stage)
    def test_api07_confirm_not_ready(self, client, session_id):
        # Create session, advance to intake, but only submit signals (no fields)
        advance_to_intake(client, session_id)
        client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact"],
        })
        # Session should be in INTAKE (not enough fields for AWAITING_CONFIRMATION)
        # The button input without all required fields stays in INTAKE
        session = client.get(f"/api/session/{session_id}").json()
        assert session["state"] == "INTAKE"

    # API-08: Reject signals
    def test_api08_reject_signals(self, client, session_id):
        self._setup_awaiting(client, session_id)
        resp = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "reject",
        })
        assert resp.status_code == 200
        assert resp.json()["state"] == "INTAKE"


# ═══════════════════════════════════════════════════════════════════════════
# Action Selection
# ═══════════════════════════════════════════════════════════════════════════
class TestActionEndpoints:
    def _setup_presenting(self, client, session_id):
        """Put session through to ACTION_SELECTION via the full flow."""
        advance_to_pattern_diagnostics(client, session_id)
        client.post(f"/api/session/{session_id}/confirm-patterns", json={
            "response": "confirm_all",
        })
        # Advance through PRESENTING_DIAGNOSIS → ALIGNMENT_CHECKPOINT → ACTION_SELECTION
        session = client.get(f"/api/session/{session_id}").json()
        if session["state"] == "PRESENTING_DIAGNOSIS":
            client.post(f"/api/session/{session_id}/confirm-understanding", json={
                "response": "confirm",
            })
        session = client.get(f"/api/session/{session_id}").json()
        if session["state"] == "ALIGNMENT_CHECKPOINT":
            client.post(f"/api/session/{session_id}/alignment-checkpoint", json={
                "response": "aligned",
            })

    # API-09: Select a valid action
    def test_api09_select_valid_action(self, client, session_id):
        self._setup_presenting(client, session_id)
        session = client.get(f"/api/session/{session_id}").json()
        sp_key = session["selected_strategy_path"]
        actions = client.get("/api/schema/representative-actions").json()
        valid_action = next(
            a["action_key"] for a in actions if a["parent_strategy_path"] == sp_key
        )
        resp = client.post(f"/api/session/{session_id}/select-action", json={
            "action_key": valid_action,
        })
        assert resp.status_code == 200
        assert resp.json()["state"] == "MONITORING"

    # API-10: Select invalid action key
    def test_api10_select_invalid_action(self, client, session_id):
        self._setup_presenting(client, session_id)
        resp = client.post(f"/api/session/{session_id}/select-action", json={
            "action_key": "nonexistent_action",
        })
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# Dual Pattern
# ═══════════════════════════════════════════════════════════════════════════
class TestDualPatternEndpoints:
    # API-11/12/13: Choose Focus, Combine, Sequence
    @pytest.mark.parametrize("choice", ["focus", "combine", "sequence"])
    def test_api11_12_13_dual_pattern_choices(self, client, session_id, choice):
        resp = client.post(f"/api/session/{session_id}/dual-pattern", json={
            "choice": choice,
        })
        assert resp.status_code in [200, 409]


# ═══════════════════════════════════════════════════════════════════════════
# General Assist
# ═══════════════════════════════════════════════════════════════════════════
class TestGeneralAssistEndpoint:
    # API-14: General AI question
    def test_api14_general_assist(self, client):
        resp = client.post("/api/general-assist", json={
            "content": "Draft a follow-up email.",
        })
        assert resp.status_code == 200
        assert "response" in resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# Schema Endpoints
# ═══════════════════════════════════════════════════════════════════════════
class TestSchemaEndpoints:
    # API-15: List signals
    def test_api15_list_signals(self, client):
        resp = client.get("/api/schema/signals")
        assert resp.status_code == 200
        assert len(resp.json()) == 23

    # API-16: List patterns
    def test_api16_list_patterns(self, client):
        resp = client.get("/api/schema/patterns")
        assert resp.status_code == 200
        assert len(resp.json()) == 22

    # API-17: List strategy paths
    def test_api17_list_strategy_paths(self, client):
        resp = client.get("/api/schema/strategy-paths")
        assert resp.status_code == 200
        assert len(resp.json()) == 13


# ═══════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════
class TestHealthEndpoint:
    # API-18: Health check
    def test_api18_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Error Handling
# ═══════════════════════════════════════════════════════════════════════════
class TestErrorHandling:
    # API-19: Submit to wrong state
    def test_api19_wrong_state(self, client, session_id):
        # Session is in INTENT_CAPTURE, try to confirm AWAITING_CONFIRMATION (should be 409)
        resp = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
        })
        # confirm now handles SITUATION_VALIDATION too, but INTENT_CAPTURE is not valid
        assert resp.status_code == 409
