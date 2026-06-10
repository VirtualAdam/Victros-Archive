"""Phase 6 — Per-Evaluation Decision Snapshot tests (DS-01 → DS-09).

TDD tests written BEFORE the DecisionSnapshot model and capture logic exist.
Every test is marked xfail so the suite stays green until implementation lands.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    advance_to_awaiting_confirmation,
    advance_to_monitoring,
    advance_to_pattern_diagnostics,
)

# ---------------------------------------------------------------------------
# Fixtures (same pattern as test_api_e2e_flow.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from server.main import create_app

    app = create_app(sessions_dir=tmp_path)
    return TestClient(app)


@pytest.fixture
def session_id(client):
    resp = client.post("/api/session/create", json={
        "user_id": "ds_user",
        "opportunity_id": "ds_opp_001",
    })
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _get_session(client: TestClient, session_id: str) -> dict:
    resp = client.get(f"/api/session/{session_id}")
    assert resp.status_code == 200
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# DS-01: DecisionSnapshot model shape
# ═══════════════════════════════════════════════════════════════════════════
class TestDS01SnapshotModelShape:
    def test_ds01_snapshot_model_shape(self):
        from server.models import DecisionSnapshot

        snap = DecisionSnapshot(
            snapshot_id="snap-001",
            session_id="sess-001",
            user_id="user_001",
            opportunity_id="opp_001",
            evaluation_run_id=1,
            timestamp="2025-07-14T12:00:00Z",
            active_signals=[{"key": "single_threaded_contact", "confidence": 0.9}],
            lever_states={
                "champion_strength": "WEAK",
                "economic_buyer_access": "WEAK",
                "case_for_change_strength": "WEAK",
                "buyer_urgency": "WEAK",
                "decision_process_control": "WEAK",
            },
            primary_pattern="single_threaded_risk",
            secondary_patterns=["competitive_displacement"],
            selected_strategy_path="selling_to_consensus",
            selected_action="run_persona_discussions",
            signal_quality_warnings=[],
        )
        assert snap.snapshot_id == "snap-001"
        assert snap.session_id == "sess-001"
        assert snap.user_id == "user_001"
        assert snap.opportunity_id == "opp_001"
        assert snap.evaluation_run_id == 1
        assert snap.timestamp == "2025-07-14T12:00:00Z"
        assert len(snap.active_signals) == 1
        assert len(snap.lever_states) == 5
        assert snap.primary_pattern == "single_threaded_risk"
        assert snap.secondary_patterns == ["competitive_displacement"]
        assert snap.selected_strategy_path == "selling_to_consensus"
        assert snap.selected_action == "run_persona_discussions"
        assert snap.signal_quality_warnings == []


# ═══════════════════════════════════════════════════════════════════════════
# DS-02: Snapshot auto-captured after evaluation
# ═══════════════════════════════════════════════════════════════════════════
class TestDS02AutoCapture:
    def test_ds02_snapshot_auto_captured_after_evaluating(self, client, session_id):
        """After a session passes through EVALUATING, it should have one
        decision snapshot with evaluation_run_id=1."""
        advance_to_pattern_diagnostics(client, session_id)

        session = _get_session(client, session_id)
        snapshots = session.get("decision_snapshots", [])
        assert len(snapshots) == 1
        assert snapshots[0]["evaluation_run_id"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# DS-03: Re-evaluation increments run_id
# ═══════════════════════════════════════════════════════════════════════════
class TestDS03ReEvaluation:
    def test_ds03_re_evaluation_increments_run_id(self, client, session_id):
        """After a second evaluation pass, the session should have 2 snapshots
        with run_ids 1 and 2."""
        advance_to_monitoring(client, session_id)

        # Trigger re-evaluation via pivot endpoint
        client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["champion_coaching_influence"],
        })
        client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
        })

        session = _get_session(client, session_id)
        snapshots = session.get("decision_snapshots", [])
        assert len(snapshots) == 2
        assert snapshots[0]["evaluation_run_id"] == 1
        assert snapshots[1]["evaluation_run_id"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# DS-04: Snapshot includes opportunity_id
# ═══════════════════════════════════════════════════════════════════════════
class TestDS04OpportunityId:
    def test_ds04_snapshot_includes_opportunity_id(self, client, session_id):
        """The captured snapshot must carry the session's opportunity_id as
        the cross-session audit key."""
        advance_to_pattern_diagnostics(client, session_id)

        session = _get_session(client, session_id)
        snapshots = session.get("decision_snapshots", [])
        assert len(snapshots) >= 1
        assert snapshots[0]["opportunity_id"] == "ds_opp_001"


# ═══════════════════════════════════════════════════════════════════════════
# DS-05: Snapshot includes per-lever scores
# ═══════════════════════════════════════════════════════════════════════════
class TestDS05PerLeverScores:
    EXPECTED_LEVERS = {
        "champion_strength",
        "economic_buyer_commitment",
        "case_for_change_strength",
        "buyer_urgency",
        "decision_process_alignment",
    }

    def test_ds05_snapshot_includes_per_lever_scores(self, client, session_id):
        """The snapshot's lever_states dict must contain all 5 core levers."""
        advance_to_pattern_diagnostics(client, session_id)

        session = _get_session(client, session_id)
        snapshots = session.get("decision_snapshots", [])
        assert len(snapshots) >= 1
        lever_keys = set(snapshots[0]["lever_states"].keys())
        assert self.EXPECTED_LEVERS.issubset(lever_keys)


# ═══════════════════════════════════════════════════════════════════════════
# DS-06: Active signals include confidence scores
# ═══════════════════════════════════════════════════════════════════════════
class TestDS06SignalConfidence:
    def test_ds06_snapshot_includes_active_signals_with_confidence(self, client, session_id):
        """Snapshot active_signals should be full ActiveSignal dicts (with
        confidence), not bare string keys."""
        advance_to_pattern_diagnostics(client, session_id)

        session = _get_session(client, session_id)
        snapshots = session.get("decision_snapshots", [])
        assert len(snapshots) >= 1
        signals = snapshots[0]["active_signals"]
        assert len(signals) >= 1
        # Each signal entry must be a dict with at least key + confidence
        for sig in signals:
            assert isinstance(sig, dict), "active_signals entries must be dicts, not bare strings"
            assert "key" in sig
            assert "confidence" in sig


# ═══════════════════════════════════════════════════════════════════════════
# DS-07: Multiple snapshots per session
# ═══════════════════════════════════════════════════════════════════════════
class TestDS07MultipleSnapshots:
    def test_ds07_multiple_snapshots_per_session(self, client, session_id):
        """After two evaluation passes the session holds exactly 2 snapshots,
        each with a distinct timestamp and run_id."""
        advance_to_monitoring(client, session_id)

        # Trigger a second evaluation
        client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["champion_coaching_influence"],
        })
        client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
        })

        session = _get_session(client, session_id)
        snapshots = session.get("decision_snapshots", [])
        assert len(snapshots) == 2
        assert snapshots[0]["evaluation_run_id"] != snapshots[1]["evaluation_run_id"]
        assert snapshots[0]["timestamp"] != snapshots[1]["timestamp"]


# ═══════════════════════════════════════════════════════════════════════════
# DS-08: Snapshot survives persistence roundtrip
# ═══════════════════════════════════════════════════════════════════════════
class TestDS08Persistence:
    def test_ds08_snapshot_stored_persistently(self, client, session_id):
        """After evaluation, re-fetching the session from storage should still
        include the decision_snapshots list."""
        advance_to_pattern_diagnostics(client, session_id)

        # First fetch — snapshot should be there
        session1 = _get_session(client, session_id)
        snapshots1 = session1.get("decision_snapshots", [])
        assert len(snapshots1) >= 1

        # Second fetch — data must survive the roundtrip
        session2 = _get_session(client, session_id)
        snapshots2 = session2.get("decision_snapshots", [])
        assert snapshots1 == snapshots2


# ═══════════════════════════════════════════════════════════════════════════
# DS-09: Snapshots are diffable between runs
# ═══════════════════════════════════════════════════════════════════════════
class TestDS09Diffable:
    def test_ds09_snapshot_diff_between_runs(self, client, session_id):
        """Two snapshots for the same session should share session_id but
        differ in evaluation_run_id, allowing meaningful diff comparisons."""
        advance_to_monitoring(client, session_id)

        # Trigger re-evaluation
        client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["champion_coaching_influence"],
        })
        client.post(f"/api/session/{session_id}/confirm", json={
            "response": "confirm",
        })

        session = _get_session(client, session_id)
        snapshots = session.get("decision_snapshots", [])
        assert len(snapshots) == 2

        snap_a, snap_b = snapshots[0], snapshots[1]
        # Same session, different evaluation
        assert snap_a["session_id"] == snap_b["session_id"]
        assert snap_a["evaluation_run_id"] != snap_b["evaluation_run_id"]
        # Structural fields present in both for diffing
        for field in ("active_signals", "lever_states", "primary_pattern"):
            assert field in snap_a
            assert field in snap_b
