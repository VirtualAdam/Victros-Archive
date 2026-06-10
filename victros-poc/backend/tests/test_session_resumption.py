"""Tier 1 — Session Resumption Tests (SR-01 → SR-10).

A user who logs out and returns must be able to see their in-progress deals
and continue from exactly where they left off. This covers:
  - list_sessions: returns sessions filtered by user_id
  - Session ordering: most recently updated first
  - Resuming a session in MONITORING state
  - API endpoint: GET /api/sessions?user_id={uid}

Written BEFORE list_sessions and the sessions API endpoint exist.
"""
import pathlib
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


@pytest.fixture
def client(tmp_path):
    from server.main import create_app
    from fastapi.testclient import TestClient

    return TestClient(create_app(sessions_dir=tmp_path))


# ═══════════════════════════════════════════════════════════════════════════
# Session Manager — list_sessions
# ═══════════════════════════════════════════════════════════════════════════
class TestListSessions:
    # SR-01: list_sessions returns sessions belonging to the given user_id
    def test_sr01_list_sessions_by_user(self, tmp_path):
        from server.session_manager import SessionManager

        mgr = SessionManager(sessions_dir=tmp_path)
        s1 = mgr.create_session(user_id="alice", opportunity_id="opp_A")
        s2 = mgr.create_session(user_id="alice", opportunity_id="opp_B")
        mgr.create_session(user_id="bob", opportunity_id="opp_C")

        alice_sessions = mgr.list_sessions(user_id="alice")
        alice_ids = [s.session_id for s in alice_sessions]

        assert s1.session_id in alice_ids
        assert s2.session_id in alice_ids
        assert len(alice_sessions) == 2

    # SR-02: list_sessions returns empty list for unknown user
    def test_sr02_empty_list_unknown_user(self, tmp_path):
        from server.session_manager import SessionManager

        mgr = SessionManager(sessions_dir=tmp_path)
        mgr.create_session(user_id="alice", opportunity_id="opp_A")

        result = mgr.list_sessions(user_id="nobody")
        assert result == []

    # SR-03: list_sessions returns sessions sorted by updated_at descending
    def test_sr03_sorted_by_updated_at_desc(self, tmp_path):
        import time
        from server.session_manager import SessionManager

        mgr = SessionManager(sessions_dir=tmp_path)
        s1 = mgr.create_session(user_id="alice", opportunity_id="opp_A")
        time.sleep(0.01)  # ensure updated_at differs
        s2 = mgr.create_session(user_id="alice", opportunity_id="opp_B")

        sessions = mgr.list_sessions(user_id="alice")
        # Most recently updated should come first
        assert sessions[0].session_id == s2.session_id
        assert sessions[1].session_id == s1.session_id

    # SR-04: Each session summary includes session_id, opportunity_id, and state
    def test_sr04_session_summary_fields(self, tmp_path):
        from server.session_manager import SessionManager

        mgr = SessionManager(sessions_dir=tmp_path)
        mgr.create_session(user_id="alice", opportunity_id="opp_A")

        sessions = mgr.list_sessions(user_id="alice")
        s = sessions[0]

        assert hasattr(s, "session_id")
        assert hasattr(s, "opportunity_id")
        assert hasattr(s, "state")
        assert s.opportunity_id == "opp_A"

    # SR-05: list_sessions returns sessions across all states
    def test_sr05_list_includes_all_states(self, tmp_path):
        from server.session_manager import SessionManager

        mgr = SessionManager(sessions_dir=tmp_path)
        s = mgr.create_session(user_id="alice", opportunity_id="opp_A")

        # Manually advance state to MONITORING
        mgr.update_state(s.session_id, "MONITORING")

        sessions = mgr.list_sessions(user_id="alice")
        assert sessions[0].state == "MONITORING"


# ═══════════════════════════════════════════════════════════════════════════
# API Endpoint — GET /api/sessions
# ═══════════════════════════════════════════════════════════════════════════
class TestSessionsAPIEndpoint:
    # SR-06: GET /api/sessions?user_id={uid} returns sessions for that user
    def test_sr06_get_sessions_endpoint(self, client):
        # Create two sessions for the same user
        client.post("/api/session/create", json={
            "user_id": "alice",
            "opportunity_id": "opp_A",
        })
        client.post("/api/session/create", json={
            "user_id": "alice",
            "opportunity_id": "opp_B",
        })
        # Create one for a different user
        client.post("/api/session/create", json={
            "user_id": "bob",
            "opportunity_id": "opp_C",
        })

        resp = client.get("/api/sessions?user_id=alice")
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) == 2
        opp_ids = [s["opportunity_id"] for s in sessions]
        assert "opp_A" in opp_ids
        assert "opp_B" in opp_ids

    # SR-07: GET /api/sessions without user_id returns 400
    def test_sr07_missing_user_id_returns_400(self, client):
        resp = client.get("/api/sessions")
        assert resp.status_code == 400

    # SR-08: GET /api/sessions?user_id={uid} for unknown user returns empty list
    def test_sr08_unknown_user_returns_empty(self, client):
        resp = client.get("/api/sessions?user_id=nobody")
        assert resp.status_code == 200
        assert resp.json() == []

    # SR-09: Sessions returned by the list endpoint are sorted most-recent-first
    def test_sr09_list_endpoint_sorted_desc(self, client):
        import time

        r1 = client.post("/api/session/create", json={
            "user_id": "alice",
            "opportunity_id": "opp_first",
        })
        time.sleep(0.01)
        r2 = client.post("/api/session/create", json={
            "user_id": "alice",
            "opportunity_id": "opp_second",
        })

        resp = client.get("/api/sessions?user_id=alice")
        sessions = resp.json()

        assert sessions[0]["opportunity_id"] == "opp_second"
        assert sessions[1]["opportunity_id"] == "opp_first"


# ═══════════════════════════════════════════════════════════════════════════
# Session Resumption — Continuing from MONITORING
# ═══════════════════════════════════════════════════════════════════════════
class TestSessionResumption:
    # SR-10: A session in MONITORING state is fully accessible via GET /api/session/{id}
    def test_sr10_resume_monitoring_session(self, client):
        from tests.conftest import advance_to_monitoring
        resp = client.post("/api/session/create", json={
            "user_id": "alice",
            "opportunity_id": "opp_deal",
        })
        sid = resp.json()["session_id"]
        advance_to_monitoring(client, sid)

        # Now simulate a "re-login" by fetching the session fresh
        resumed = client.get(f"/api/session/{sid}").json()
        assert resumed["state"] == "MONITORING"
        assert resumed["session_id"] == sid
        assert resumed["selected_strategy_path"] is not None
