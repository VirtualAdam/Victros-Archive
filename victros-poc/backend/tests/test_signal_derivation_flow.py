"""Tier SD — Signal Derivation Flow Tests (SD-01 → SD-06).

End-to-end tests verifying the system-derived signal extraction flow:
  1. User completes intake fields
  2. System auto-extracts candidate signals with confidence scores
  3. User reviews and confirms/rejects derived signals
  4. Confirmed signals proceed to evaluation

All tests are marked xfail because the extraction endpoint and
signal derivation logic do not exist yet. These define the expected
API contract for Phase 1 implementation.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import advance_to_intake, submit_all_required_fields


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client(tmp_path):
    """TestClient with isolated session storage."""
    from server.main import create_app

    app = create_app(sessions_dir=tmp_path)
    return TestClient(app)


@pytest.fixture
def session_id(client):
    """Create a fresh session and return its ID."""
    resp = client.post("/api/session/create", json={
        "user_id": "sd_test_user",
        "opportunity_id": "sd_test_opp",
    })
    assert resp.status_code == 201
    return resp.json()["session_id"]


@pytest.fixture
def session_at_intake(client, session_id):
    """Drive session to INTAKE state and return session_id."""
    advance_to_intake(client, session_id)
    return session_id


# ═══════════════════════════════════════════════════════════════════════════
# SD-01: Intake Completion Triggers Signal Extraction (SRS 1.6)
# ═══════════════════════════════════════════════════════════════════════════


class TestIntakeTriggersExtraction:
    def test_sd01_intake_complete_triggers_extraction(self, client, session_at_intake):
        """After all required intake fields are submitted, the response
        should include a 'derived_signals' list of candidate signals
        instead of requiring manual signal selection."""
        session_id = session_at_intake

        # Submit all required intake fields
        resp = client.post(f"/api/session/{session_id}/input", json={
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
        assert resp.status_code == 200
        data = resp.json()

        # The response should now include derived signals for review
        assert "derived_signals" in data, (
            "Intake completion should return derived_signals for user review"
        )
        assert isinstance(data["derived_signals"], list)
        assert len(data["derived_signals"]) > 0


# ═══════════════════════════════════════════════════════════════════════════
# SD-02: Extraction Returns Confidence Scores (SRS 1.2)
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractionConfidenceScores:
    def test_sd02_extraction_returns_confidence_scores(self, client, session_at_intake):
        """Each derived signal must include a confidence score between 0 and 1."""
        session_id = session_at_intake

        resp = client.post(f"/api/session/{session_id}/input", json={
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
        data = resp.json()
        assert "derived_signals" in data

        for sig in data["derived_signals"]:
            assert "key" in sig, "Each derived signal must have a 'key'"
            assert "confidence" in sig, "Each derived signal must have a 'confidence'"
            assert 0.0 <= sig["confidence"] <= 1.0, (
                f"Confidence for {sig['key']} must be in [0, 1], got {sig['confidence']}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# SD-03: Derived Signals Replace Manual Selection (SRS 1.6)
# ═══════════════════════════════════════════════════════════════════════════


class TestDerivedSignalsReplaceManual:
    def test_sd03_derived_signals_replace_manual_selection(
        self, client, session_at_intake
    ):
        """When derived signals are present, submitting them (not manually
        selecting from the full list) should transition to AWAITING_CONFIRMATION."""
        session_id = session_at_intake
        submit_all_required_fields(client, session_id)

        # Fetch the session to get derived signals
        session_resp = client.get(f"/api/session/{session_id}")
        session_data = session_resp.json()

        # The session should contain derived signal candidates
        assert "derived_signals" in session_data or "candidate_signals" in session_data

        # Confirm derived signals (new flow replaces manual button/signals selection)
        resp = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "confirm_derived_signals",
            "accepted_signals": ["single_threaded_contact"],
            "rejected_signals": [],
        })
        assert resp.status_code == 200
        assert resp.json()["state"] == "AWAITING_CONFIRMATION"


# ═══════════════════════════════════════════════════════════════════════════
# SD-04: User Can Reject Derived Signal (SRS 1.6)
# ═══════════════════════════════════════════════════════════════════════════


class TestUserRejectDerivedSignal:
    def test_sd04_user_can_reject_derived_signal(self, client, session_at_intake):
        """A user should be able to reject a derived signal, and it should
        NOT appear in the session's active_signals after confirmation."""
        session_id = session_at_intake
        submit_all_required_fields(client, session_id)

        # Confirm with one signal accepted and one rejected
        resp = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "confirm_derived_signals",
            "accepted_signals": ["champion_coaching_influence"],
            "rejected_signals": ["single_threaded_contact"],
        })
        assert resp.status_code == 200

        # Fetch the session and check active signals
        session_resp = client.get(f"/api/session/{session_id}")
        session_data = session_resp.json()
        active = session_data.get("active_signals", [])

        assert "champion_coaching_influence" in active
        assert "single_threaded_contact" not in active


# ═══════════════════════════════════════════════════════════════════════════
# SD-05: User Confirm Proceeds to EVALUATING (SRS 1.6)
# ═══════════════════════════════════════════════════════════════════════════


class TestUserConfirmProceeds:
    def test_sd05_user_confirm_proceeds_to_evaluating(self, client, session_at_intake):
        """After user confirms derived signals, /confirm should transition
        the session through to evaluation (AWAITING_CONFIRMATION → EVALUATING
        or equivalent downstream state)."""
        session_id = session_at_intake
        submit_all_required_fields(client, session_id)

        # Accept derived signals
        client.post(f"/api/session/{session_id}/input", json={
            "input_type": "confirm_derived_signals",
            "accepted_signals": ["single_threaded_contact"],
            "rejected_signals": [],
        })

        # Confirm to proceed
        resp = client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
            "deal_stage": "3_Validation",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Should have progressed past AWAITING_CONFIRMATION
        assert data["state"] in (
            "EVALUATING",
            "PATTERN_DIAGNOSTICS",
        ), f"Expected EVALUATING or PATTERN_DIAGNOSTICS, got {data['state']}"


# ═══════════════════════════════════════════════════════════════════════════
# SD-06: Normalization Maps Vague Input (SRS 1.6)
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizationMapsVagueInput:
    def test_sd06_normalization_maps_vague_input(self, client, session_at_intake):
        """When a user provides vague or colloquial descriptions in intake fields,
        the derivation engine should still map them to relevant signals."""
        session_id = session_at_intake

        # Submit fields with vague/colloquial language
        resp = client.post(f"/api/session/{session_id}/input", json={
            "input_type": "fields",
            "fields": {
                "deal_stage": "3_Validation",
                "offering_type": "product",
                "offering_usage": "yes",
                "usage_depth": "deep",
                "deal_amount": "500000",
                "close_date": "2025-06-30",
                # Vague descriptions that imply single-threaded risk
                "stakeholder_notes": "Only talking to one guy, the IT manager",
                "champion_status": "not sure who would champion this internally",
            },
        })
        assert resp.status_code == 200
        data = resp.json()

        # Even with vague language, system should derive relevant signals
        assert "derived_signals" in data
        derived_keys = [s["key"] for s in data["derived_signals"]]

        # At least one of these signals should be derived from the vague input
        relevant_signals = {
            "single_threaded_contact",
            "no_named_or_active_champion",
        }
        assert relevant_signals & set(derived_keys), (
            f"Expected at least one of {relevant_signals} from vague input, "
            f"got {derived_keys}"
        )
