"""Tier TDD — Alignment Checkpoint Tests (AC-01 → AC-07).

Phase 4: ALIGNMENT_CHECKPOINT sits between PRESENTING_DIAGNOSIS and ACTION_SELECTION.
After the system presents its diagnosis, the user must explicitly confirm alignment
before proceeding to action selection. This prevents users from acting on a misunderstood
diagnosis.

Written BEFORE the ALIGNMENT_CHECKPOINT state exists.
All tests are xfail until the state machine and endpoints are implemented.
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
        "user_id": "ac_user",
        "opportunity_id": "ac_opp",
    })
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _get_state(client: TestClient, session_id: str) -> str:
    resp = client.get(f"/api/session/{session_id}")
    assert resp.status_code == 200
    return resp.json()["state"]


def _drive_to_presenting_diagnosis(client: TestClient, session_id: str) -> dict:
    """Drive a session to PRESENTING_DIAGNOSIS via the standard flow."""
    advance_to_pattern_diagnostics(client, session_id)
    r = client.post(f"/api/session/{session_id}/confirm-patterns", json={
        "response": "confirm_all",
    })
    assert r.status_code == 200
    data = r.json()
    # Currently may land in PRESENTING_DIAGNOSIS or ACTION_SELECTION;
    # once checkpoint is implemented it should always hit PRESENTING_DIAGNOSIS first.
    return data


# ═══════════════════════════════════════════════════════════════════════════
# AC-01: Checkpoint state is reached after diagnosis
# ═══════════════════════════════════════════════════════════════════════════


class TestAC01_CheckpointReachedAfterDiagnosis:
    """After PRESENTING_DIAGNOSIS, the next state should be ALIGNMENT_CHECKPOINT."""

    def test_ac01_checkpoint_state_reached_after_diagnosis(self, client, session_id):
        data = _drive_to_presenting_diagnosis(client, session_id)

        if data["state"] == "PRESENTING_DIAGNOSIS":
            # Confirm understanding to advance
            r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
                "response": "confirm",
            })
            assert r.status_code == 200
            data = r.json()

        assert data["state"] == "ALIGNMENT_CHECKPOINT", (
            f"Expected ALIGNMENT_CHECKPOINT after diagnosis, got {data['state']}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AC-02: "aligned" proceeds to ACTION_SELECTION
# ═══════════════════════════════════════════════════════════════════════════


class TestAC02_AlignedProceedsToActionSelection:
    """At ALIGNMENT_CHECKPOINT, sending 'aligned' transitions to ACTION_SELECTION."""

    def test_ac02_aligned_proceeds_to_action_selection(self, client, session_id):
        data = _drive_to_presenting_diagnosis(client, session_id)

        if data["state"] == "PRESENTING_DIAGNOSIS":
            r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
                "response": "confirm",
            })
            data = r.json()

        assert data["state"] == "ALIGNMENT_CHECKPOINT"

        r = client.post(f"/api/session/{session_id}/alignment-checkpoint", json={
            "response": "aligned",
        })
        assert r.status_code == 200
        assert r.json()["state"] == "ACTION_SELECTION"


# ═══════════════════════════════════════════════════════════════════════════
# AC-03: "does_not_match" returns to signal review
# ═══════════════════════════════════════════════════════════════════════════


class TestAC03_DoesNotMatchReturnsToSignalReview:
    """At ALIGNMENT_CHECKPOINT, 'does_not_match' returns to INTAKE for signal review."""

    def test_ac03_does_not_match_returns_to_signal_review(self, client, session_id):
        data = _drive_to_presenting_diagnosis(client, session_id)

        if data["state"] == "PRESENTING_DIAGNOSIS":
            r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
                "response": "confirm",
            })
            data = r.json()

        assert data["state"] == "ALIGNMENT_CHECKPOINT"

        r = client.post(f"/api/session/{session_id}/alignment-checkpoint", json={
            "response": "does_not_match",
        })
        assert r.status_code == 200
        assert r.json()["state"] in ("INTAKE", "SIGNAL_REVIEW"), (
            f"Expected INTAKE or SIGNAL_REVIEW, got {r.json()['state']}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AC-04: "something_changed" prompts context update
# ═══════════════════════════════════════════════════════════════════════════


class TestAC04_SomethingChangedPromptsContextUpdate:
    """At ALIGNMENT_CHECKPOINT, 'something_changed' triggers re-entry flow."""

    def test_ac04_something_changed_prompts_context_update(self, client, session_id):
        data = _drive_to_presenting_diagnosis(client, session_id)

        if data["state"] == "PRESENTING_DIAGNOSIS":
            r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
                "response": "confirm",
            })
            data = r.json()

        assert data["state"] == "ALIGNMENT_CHECKPOINT"

        r = client.post(f"/api/session/{session_id}/alignment-checkpoint", json={
            "response": "something_changed",
        })
        assert r.status_code == 200
        new_state = r.json()["state"]
        # Re-entry: goes back to intake or situation validation to update context
        assert new_state in ("INTAKE", "SITUATION_VALIDATION", "INTENT_CAPTURE"), (
            f"Expected re-entry state, got {new_state}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AC-05: "new_session" creates a fresh session
# ═══════════════════════════════════════════════════════════════════════════


class TestAC05_NewSessionCreatesFreshSession:
    """At ALIGNMENT_CHECKPOINT, 'new_session' creates a brand new session."""

    def test_ac05_new_session_creates_fresh_session(self, client, session_id):
        data = _drive_to_presenting_diagnosis(client, session_id)

        if data["state"] == "PRESENTING_DIAGNOSIS":
            r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
                "response": "confirm",
            })
            data = r.json()

        assert data["state"] == "ALIGNMENT_CHECKPOINT"

        r = client.post(f"/api/session/{session_id}/alignment-checkpoint", json={
            "response": "new_session",
        })
        assert r.status_code == 200
        resp_data = r.json()
        # Should either create a new session or transition to a fresh start state
        if "session_id" in resp_data:
            assert resp_data["session_id"] != session_id
            assert resp_data["state"] == "INTENT_CAPTURE"
        else:
            assert resp_data["state"] == "INTENT_CAPTURE"


# ═══════════════════════════════════════════════════════════════════════════
# AC-06: Checkpoint displays pattern and levers
# ═══════════════════════════════════════════════════════════════════════════


class TestAC06_CheckpointDisplaysPatternAndLevers:
    """Response at ALIGNMENT_CHECKPOINT includes primary_pattern, lever_states, strategy_path."""

    def test_ac06_checkpoint_displays_pattern_and_levers(self, client, session_id):
        data = _drive_to_presenting_diagnosis(client, session_id)

        if data["state"] == "PRESENTING_DIAGNOSIS":
            r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
                "response": "confirm",
            })
            data = r.json()

        assert data["state"] == "ALIGNMENT_CHECKPOINT"

        # The checkpoint response should include a summary of the diagnosis
        assert "primary_pattern" in data, "Checkpoint must include primary_pattern"
        assert "lever_states" in data, "Checkpoint must include lever_states"
        assert "strategy_path" in data, "Checkpoint must include strategy_path summary"


# ═══════════════════════════════════════════════════════════════════════════
# AC-07: Cannot skip directly from PRESENTING_DIAGNOSIS to ACTION_SELECTION
# ═══════════════════════════════════════════════════════════════════════════


class TestAC07_CheckpointBlocksDirectSkipToAction:
    """PRESENTING_DIAGNOSIS → ACTION_SELECTION must be blocked (must go through checkpoint)."""

    def test_ac07_checkpoint_blocks_direct_skip_to_action(self):
        from server.state_machine import validate_transition

        # Once ALIGNMENT_CHECKPOINT is added, direct skip should be invalid
        assert validate_transition("PRESENTING_DIAGNOSIS", "ACTION_SELECTION") is False, (
            "Direct PRESENTING_DIAGNOSIS → ACTION_SELECTION should be blocked; "
            "must go through ALIGNMENT_CHECKPOINT"
        )
