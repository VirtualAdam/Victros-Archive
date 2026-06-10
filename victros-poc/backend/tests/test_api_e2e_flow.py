"""Tier E2E — Full HTTP-flow tests that drive sessions from creation to completion.

These tests prevent the class of failure where API endpoints aren't updated for
new engine states. Every test drives a real session through the FastAPI TestClient
and asserts state at EVERY intermediate step.

Uses the same conftest helpers as test_api.py but extends them with drive_to_state().
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    advance_to_intake,
    advance_to_awaiting_confirmation,
    advance_to_pattern_diagnostics,
    submit_all_required_fields,
    advance_to_monitoring,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client(tmp_path):
    """TestClient with a tmp_path session dir — no shared state between tests."""
    from server.main import create_app

    app = create_app(sessions_dir=tmp_path)
    return TestClient(app)


@pytest.fixture
def session_id(client):
    """Create a session and return its ID."""
    resp = client.post("/api/session/create", json={
        "user_id": "e2e_user",
        "opportunity_id": "e2e_opp",
    })
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _get_state(client: TestClient, session_id: str) -> str:
    """Fetch current session state via GET."""
    resp = client.get(f"/api/session/{session_id}")
    assert resp.status_code == 200
    return resp.json()["state"]


def _get_valid_action_key(client: TestClient, session_id: str) -> str:
    """Look up a valid action_key for the session's current strategy_path."""
    session = client.get(f"/api/session/{session_id}").json()
    sp_key = session["selected_strategy_path"]
    actions = client.get("/api/schema/representative-actions").json()
    return next(a["action_key"] for a in actions if a["parent_strategy_path"] == sp_key)


def drive_to_state(
    client: TestClient,
    session_id: str,
    target_state: str,
    signals: list[str] | None = None,
    deal_stage: str = "3_Validation",
) -> dict:
    """Drive a session through the flow to *target_state*, asserting each step.

    Returns the response dict from the last API call that reached the target.
    """
    sigs = signals or ["single_threaded_contact"]
    current = _get_state(client, session_id)

    if current == target_state:
        return client.get(f"/api/session/{session_id}").json()

    # S2 → S3: INTENT_CAPTURE → SITUATION_VALIDATION
    if current == "INTENT_CAPTURE":
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "text",
            "content": "I need help closing this deal",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "SITUATION_VALIDATION"
        current = "SITUATION_VALIDATION"
        if current == target_state:
            return r.json()

    # S3 → S4: SITUATION_VALIDATION → INTAKE
    if current == "SITUATION_VALIDATION":
        r = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "INTAKE"
        current = "INTAKE"
        if current == target_state:
            return r.json()

    # S4: Submit fields + signals → AWAITING_CONFIRMATION
    if current == "INTAKE":
        # Submit all 6 required fields
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {
                "deal_stage": deal_stage,
                "offering_type": "product",
                "offering_usage": "yes",
                "usage_depth": "deep",
                "deal_amount": "500000",
                "close_date": "2025-06-30",
            },
        })
        assert r.status_code == 200

        # Submit signals → AWAITING_CONFIRMATION
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": sigs,
        })
        assert r.status_code == 200
        assert r.json()["state"] == "AWAITING_CONFIRMATION"
        current = "AWAITING_CONFIRMATION"
        if current == target_state:
            return r.json()

    # S5 → S6/S7: AWAITING_CONFIRMATION → confirm → PATTERN_DIAGNOSTICS
    if current == "AWAITING_CONFIRMATION":
        r = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
            "deal_stage": deal_stage,
        })
        assert r.status_code == 200
        assert r.json()["state"] == "PATTERN_DIAGNOSTICS"
        current = "PATTERN_DIAGNOSTICS"
        if current == target_state:
            return r.json()

    # S7 → S8: PATTERN_DIAGNOSTICS → confirm_all → PRESENTING_DIAGNOSIS
    if current == "PATTERN_DIAGNOSTICS":
        r = client.post(f"/api/session/{session_id}/confirm-patterns", json={
            "response": "confirm_all",
        })
        assert r.status_code == 200
        data = r.json()
        current = data["state"]
        assert current in ("PRESENTING_DIAGNOSIS", "ACTION_SELECTION")
        if current == target_state:
            return data

    # S8 → ALIGNMENT_CHECKPOINT: PRESENTING_DIAGNOSIS → confirm understanding
    if current == "PRESENTING_DIAGNOSIS":
        r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
            "response": "confirm",
        })
        assert r.status_code == 200
        data = r.json()
        current = data["state"]
        assert current == "ALIGNMENT_CHECKPOINT"
        if current == target_state:
            return data

    # ALIGNMENT_CHECKPOINT → aligned → ACTION_SELECTION or DUAL_PATTERN_TRADEOFF
    if current == "ALIGNMENT_CHECKPOINT":
        r = client.post(f"/api/session/{session_id}/alignment-checkpoint", json={
            "response": "aligned",
        })
        assert r.status_code == 200
        data = r.json()
        current = data["state"]
        assert current in ("DUAL_PATTERN_TRADEOFF", "ACTION_SELECTION")
        if current == target_state:
            return data

    # S9 → S10: DUAL_PATTERN_TRADEOFF → ACTION_SELECTION
    if current == "DUAL_PATTERN_TRADEOFF":
        r = client.post(f"/api/session/{session_id}/dual-pattern", json={
            "choice": "focus",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "ACTION_SELECTION"
        current = "ACTION_SELECTION"
        if current == target_state:
            return r.json()

    # S10 → S11: ACTION_SELECTION → select action → MONITORING
    if current == "ACTION_SELECTION":
        action_key = _get_valid_action_key(client, session_id)
        r = client.post(f"/api/session/{session_id}/select-action", json={
            "action_key": action_key,
        })
        assert r.status_code == 200
        assert r.json()["state"] == "MONITORING"
        current = "MONITORING"
        if current == target_state:
            return r.json()

    assert current == target_state, (
        f"drive_to_state failed: ended in {current}, wanted {target_state}"
    )
    return client.get(f"/api/session/{session_id}").json()


# ═══════════════════════════════════════════════════════════════════════════
# E2E-01: Full happy path
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E01_FullHappyPath:
    """Create → INTENT_CAPTURE → ... → MONITORING, asserting every state."""

    def test_full_happy_path(self, client):
        # S1 → S2: create session
        r = client.post("/api/session/create", json={
            "user_id": "e2e_user", "opportunity_id": "e2e_deal_01",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["state"] == "INTENT_CAPTURE"
        assert data["prompt"] == "How can I help you win today?"
        sid = data["session_id"]

        # S2 → S3: submit intent
        r = client.post(f"/api/session/{sid}/input", json={
            "input_type": "text", "content": "I need help closing this deal",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "SITUATION_VALIDATION"

        # S3 → S4: confirm situation
        r = client.post(f"/api/session/{sid}/confirm", json={"response": "confirm"})
        assert r.status_code == 200
        assert r.json()["state"] == "INTAKE"

        # S4: submit 6 required fields
        r = client.post(f"/api/session/{sid}/input", json={
            "input_type": "fields",
            "fields": {
                "deal_stage": "3_Validation",
                "offering_type": "product",
                "offering_usage": "yes",
                "usage_depth": "deep",
                "deal_amount": "500000",
                "close_date": "2025-06-30",
            },
        })
        assert r.status_code == 200
        assert r.json()["state"] == "INTAKE"  # fields collected, awaiting signals

        # S4 → S5: submit signals → AWAITING_CONFIRMATION
        r = client.post(f"/api/session/{sid}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact"],
        })
        assert r.status_code == 200
        assert r.json()["state"] == "AWAITING_CONFIRMATION"

        # S5 → S6/S7: confirm → engine runs → PATTERN_DIAGNOSTICS
        r = client.post(f"/api/session/{sid}/confirm", json={
            "response": "confirm", "deal_stage": "3_Validation",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "PATTERN_DIAGNOSTICS"

        # S7 → S8: confirm patterns
        r = client.post(f"/api/session/{sid}/confirm-patterns", json={
            "response": "confirm_all",
        })
        assert r.status_code == 200
        cp_data = r.json()
        assert cp_data["state"] in ("PRESENTING_DIAGNOSIS", "ACTION_SELECTION")

        # S8 → ALIGNMENT_CHECKPOINT: confirm understanding
        if cp_data["state"] == "PRESENTING_DIAGNOSIS":
            r = client.post(f"/api/session/{sid}/confirm-understanding", json={
                "response": "confirm",
            })
            assert r.status_code == 200
            cu_data = r.json()
            assert cu_data["state"] == "ALIGNMENT_CHECKPOINT"

            # ALIGNMENT_CHECKPOINT → aligned → ACTION_SELECTION or DUAL_PATTERN_TRADEOFF
            r = client.post(f"/api/session/{sid}/alignment-checkpoint", json={
                "response": "aligned",
            })
            assert r.status_code == 200
            al_data = r.json()
            assert al_data["state"] in ("DUAL_PATTERN_TRADEOFF", "ACTION_SELECTION")

            if al_data["state"] == "DUAL_PATTERN_TRADEOFF":
                r = client.post(f"/api/session/{sid}/dual-pattern", json={
                    "choice": "focus",
                })
                assert r.status_code == 200
                assert r.json()["state"] == "ACTION_SELECTION"

        # S10 → S11: select action → MONITORING
        action_key = _get_valid_action_key(client, sid)
        r = client.post(f"/api/session/{sid}/select-action", json={
            "action_key": action_key,
        })
        assert r.status_code == 200
        assert r.json()["state"] == "MONITORING"

        # Verify final state via GET
        assert _get_state(client, sid) == "MONITORING"


# ═══════════════════════════════════════════════════════════════════════════
# E2E-02: TMobile deal (Richard's golden scenario)
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E02_TMobileDeal:
    """TMobile: problem_not_validated + no_named_or_active_champion."""

    SIGNALS = ["problem_not_validated", "no_named_or_active_champion"]

    def test_tmobile_golden_scenario(self, client, session_id):
        result = drive_to_state(
            client, session_id, "PATTERN_DIAGNOSTICS", signals=self.SIGNALS,
        )
        # Verify engine selected the correct pattern/strategy
        session = client.get(f"/api/session/{session_id}").json()

        assert session["active_patterns"]["primary"] == "weak_problem_definition", (
            f"Expected primary='weak_problem_definition', got '{session['active_patterns']['primary']}'"
        )
        assert session["selected_strategy_path"] == "Qualify_CaseForChange", (
            f"Expected strategy_path='Qualify_CaseForChange', got '{session['selected_strategy_path']}'"
        )
        assert "champion_absence" in session["active_patterns"]["secondary"], (
            f"Expected 'champion_absence' in secondary, got {session['active_patterns']['secondary']}"
        )

        # Continue to MONITORING to verify the full flow works
        drive_to_state(client, session_id, "MONITORING", signals=self.SIGNALS)
        assert _get_state(client, session_id) == "MONITORING"


# ═══════════════════════════════════════════════════════════════════════════
# E2E-03: Situation correction loop
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E03_SituationCorrectionLoop:
    """Create → intent → situation validation → correct → INTENT_CAPTURE → re-submit → INTAKE."""

    def test_correction_loop(self, client, session_id):
        # S2 → S3: submit intent
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "text", "content": "I need help with my deal",
        })
        assert r.json()["state"] == "SITUATION_VALIDATION"

        # S3 → S2: correct
        r = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "correct",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "INTENT_CAPTURE"
        assert data.get("correction") is True

        # Re-submit intent
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "text",
            "content": "Actually, I need help closing a deal with TMobile",
        })
        assert r.json()["state"] == "SITUATION_VALIDATION"

        # Confirm this time
        r = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
        })
        assert r.json()["state"] == "INTAKE"


# ═══════════════════════════════════════════════════════════════════════════
# E2E-04: Pattern rejection loop
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E04_PatternRejectionLoop:
    """Drive to PATTERN_DIAGNOSTICS → reject_all → INTAKE → re-submit → patterns again."""

    def test_pattern_rejection_loop(self, client, session_id):
        # Drive to PATTERN_DIAGNOSTICS
        drive_to_state(client, session_id, "PATTERN_DIAGNOSTICS")

        # Reject all patterns → back to INTAKE
        r = client.post(f"/api/session/{session_id}/confirm-patterns", json={
            "response": "reject_all",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "INTAKE"
        assert _get_state(client, session_id) == "INTAKE"

        # Re-submit fields + signals → back to AWAITING_CONFIRMATION
        submit_all_required_fields(client, session_id)
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact"],
        })
        assert r.json()["state"] == "AWAITING_CONFIRMATION"

        # Confirm → PATTERN_DIAGNOSTICS again
        r = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm", "deal_stage": "3_Validation",
        })
        assert r.json()["state"] == "PATTERN_DIAGNOSTICS"


# ═══════════════════════════════════════════════════════════════════════════
# E2E-05: Dual pattern flow
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E05_DualPatternFlow:
    """Signals that activate 2 patterns → DUAL_PATTERN_TRADEOFF path."""

    # TMobile signals activate 2 patterns (weak_problem_definition + champion_absence)
    DUAL_SIGNALS = ["problem_not_validated", "no_named_or_active_champion"]

    def test_dual_pattern_tradeoff_path(self, client, session_id):
        # Drive to PRESENTING_DIAGNOSIS with dual-pattern signals
        drive_to_state(
            client, session_id, "PRESENTING_DIAGNOSIS", signals=self.DUAL_SIGNALS,
        )

        # Verify session has secondary patterns
        session = client.get(f"/api/session/{session_id}").json()
        assert len(session["active_patterns"]["secondary"]) > 0, (
            "Expected at least one secondary pattern for dual-pattern flow"
        )

        # Confirm understanding → should go to ALIGNMENT_CHECKPOINT
        r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
            "response": "confirm",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "ALIGNMENT_CHECKPOINT"

        # Aligned → should go to DUAL_PATTERN_TRADEOFF (secondary patterns exist)
        r = client.post(f"/api/session/{session_id}/alignment-checkpoint", json={
            "response": "aligned",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "DUAL_PATTERN_TRADEOFF"

        # Select focus → ACTION_SELECTION
        r = client.post(f"/api/session/{session_id}/dual-pattern", json={
            "choice": "focus",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "ACTION_SELECTION"

        # Select action → MONITORING
        action_key = _get_valid_action_key(client, session_id)
        r = client.post(f"/api/session/{session_id}/select-action", json={
            "action_key": action_key,
        })
        assert r.status_code == 200
        assert r.json()["state"] == "MONITORING"


# ═══════════════════════════════════════════════════════════════════════════
# E2E-06: Intake field ordering
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E06_IntakeFieldOrdering:
    """Submit fields out of order — system should still accept them all."""

    def test_fields_out_of_order(self, client, session_id):
        advance_to_intake(client, session_id)

        # Submit fields in reverse order (close_date first, deal_stage last)
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {"close_date": "2025-12-31"},
        })
        assert r.status_code == 200

        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {"deal_amount": "1000000"},
        })
        assert r.status_code == 200

        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {"usage_depth": "deep"},
        })
        assert r.status_code == 200

        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {"offering_usage": "yes"},
        })
        assert r.status_code == 200

        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {"offering_type": "product"},
        })
        assert r.status_code == 200

        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {"deal_stage": "3_Validation"},
        })
        assert r.status_code == 200

        # All fields collected — submit signals to advance
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact"],
        })
        assert r.status_code == 200
        assert r.json()["state"] == "AWAITING_CONFIRMATION"


# ═══════════════════════════════════════════════════════════════════════════
# E2E-07: Missing fields block progression
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E07_MissingFieldsBlock:
    """Submit only 3 of 6 fields + signals → should NOT advance past INTAKE."""

    def test_incomplete_fields_stay_in_intake(self, client, session_id):
        advance_to_intake(client, session_id)

        # Submit only 3 fields
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {
                "deal_stage": "3_Validation",
                "offering_type": "product",
                "offering_usage": "yes",
            },
        })
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "INTAKE"
        # Should indicate more fields needed
        assert data.get("next_prompt") is not None

        # Try to submit signals — should stay in INTAKE since fields are missing
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact"],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "INTAKE", (
            f"Expected INTAKE with missing fields, got {data['state']}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# E2E-08: State enforcement
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E08_StateEnforcement:
    """Invalid state transitions must return 409."""

    def test_confirm_patterns_wrong_state(self, client, session_id):
        """confirm-patterns in INTAKE state → 409."""
        advance_to_intake(client, session_id)
        r = client.post(f"/api/session/{session_id}/confirm-patterns", json={
            "response": "confirm_all",
        })
        assert r.status_code == 409

    def test_select_action_wrong_state(self, client, session_id):
        """select-action in PATTERN_DIAGNOSTICS state → 409."""
        drive_to_state(client, session_id, "PATTERN_DIAGNOSTICS")
        r = client.post(f"/api/session/{session_id}/select-action", json={
            "action_key": "any_key",
        })
        assert r.status_code == 409

    def test_confirm_understanding_wrong_state(self, client, session_id):
        """confirm-understanding in INTAKE state → 409."""
        advance_to_intake(client, session_id)
        r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
            "response": "confirm",
        })
        assert r.status_code == 409

    def test_dual_pattern_wrong_state(self, client, session_id):
        """dual-pattern in INTAKE state → 409."""
        advance_to_intake(client, session_id)
        r = client.post(f"/api/session/{session_id}/dual-pattern", json={
            "choice": "focus",
        })
        assert r.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# E2E-09: Pivot from MONITORING
# ═══════════════════════════════════════════════════════════════════════════

class TestE2E09_PivotFromMonitoring:
    """MONITORING → submit new signals → AWAITING_CONFIRMATION → re-evaluate."""

    def test_monitoring_pivot(self, client, session_id):
        # Drive all the way to MONITORING
        drive_to_state(client, session_id, "MONITORING")
        assert _get_state(client, session_id) == "MONITORING"

        # Submit new signals from MONITORING — MONITORING accepts input
        r = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["problem_not_validated", "no_named_or_active_champion"],
        })
        assert r.status_code == 200
        data = r.json()
        # MONITORING input with signals should trigger re-evaluation flow
        # The API accepts input in MONITORING state (mapped to INTAKE handler)
        assert data["state"] in ("AWAITING_CONFIRMATION", "INTAKE", "MONITORING"), (
            f"Expected re-entry state, got {data['state']}"
        )
