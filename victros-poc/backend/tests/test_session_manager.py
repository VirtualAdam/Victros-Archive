"""Tier 1 — Session Manager Tests (SM-01 → SM-14).

Written BEFORE session_manager.py exists.
Uses temp directories to avoid polluting disk.
"""
import tempfile
import pathlib
import pytest


@pytest.fixture
def mgr(tmp_path):
    from server.session_manager import SessionManager

    return SessionManager(tmp_path)


# ---------------------------------------------------------------------------
class TestSessionManagerCRUD:
    # SM-01: Create a new session
    def test_sm01_create_session(self, mgr):
        session = mgr.create_session(user_id="user_001", opportunity_id="opp_acme")
        assert session.session_id  # non-empty UUID
        assert session.user_id == "user_001"
        assert session.opportunity_id == "opp_acme"
        assert session.state == "NEW_SESSION"
        assert all(v == "WEAK" for v in session.lever_states.values())
        assert session.intake_readiness.deal_stage == "missing"

    # SM-02: Get session by ID
    def test_sm02_get_session(self, mgr):
        created = mgr.create_session("user_001", "opp_acme")
        fetched = mgr.get_session(created.session_id)
        assert fetched is not None
        assert fetched.session_id == created.session_id

    # SM-03: Get non-existent session
    def test_sm03_get_nonexistent(self, mgr):
        result = mgr.get_session("does-not-exist")
        assert result is None

    # SM-04: Update active_signals
    def test_sm04_update_signals(self, mgr):
        session = mgr.create_session("user_001", "opp_acme")
        mgr.update_session(session.session_id, active_signals=["single_threaded_contact"])
        fetched = mgr.get_session(session.session_id)
        assert fetched.active_signals == ["single_threaded_contact"]

    # SM-05: Update deal_snapshot
    def test_sm05_update_deal_snapshot(self, mgr):
        from server.models import DealSnapshot

        session = mgr.create_session("user_001", "opp_acme")
        snap = DealSnapshot(stage="3_Validation", amount=1200000)
        mgr.update_session(session.session_id, deal_snapshot=snap)
        fetched = mgr.get_session(session.session_id)
        assert fetched.deal_snapshot.stage == "3_Validation"
        assert fetched.deal_snapshot.amount == 1200000

    # SM-06: Update lever_states
    def test_sm06_update_lever_states(self, mgr):
        session = mgr.create_session("user_001", "opp_acme")
        new_levers = session.lever_states.copy()
        new_levers["champion_strength"] = "CONNECTED"
        mgr.update_session(session.session_id, lever_states=new_levers)
        fetched = mgr.get_session(session.session_id)
        assert fetched.lever_states["champion_strength"] == "CONNECTED"

    # SM-07: Update active_patterns
    def test_sm07_update_patterns(self, mgr):
        from server.models import ActivePatterns

        session = mgr.create_session("user_001", "opp_acme")
        patterns = ActivePatterns(primary="single_threaded_risk", secondary=["competitive_displacement"])
        mgr.update_session(session.session_id, active_patterns=patterns)
        fetched = mgr.get_session(session.session_id)
        assert fetched.active_patterns.primary == "single_threaded_risk"
        assert "competitive_displacement" in fetched.active_patterns.secondary

    # SM-08: Update selected_strategy_path
    def test_sm08_update_strategy_path(self, mgr):
        session = mgr.create_session("user_001", "opp_acme")
        mgr.update_session(session.session_id, selected_strategy_path="selling_to_consensus")
        fetched = mgr.get_session(session.session_id)
        assert fetched.selected_strategy_path == "selling_to_consensus"

    # SM-09: Append to interaction_history
    def test_sm09_append_history(self, mgr):
        session = mgr.create_session("user_001", "opp_acme")
        entry = {"type": "user_input", "content": "test message"}
        mgr.append_history(session.session_id, entry)
        fetched = mgr.get_session(session.session_id)
        assert len(fetched.interaction_history) == 1
        assert fetched.interaction_history[0]["content"] == "test message"

    # SM-10: Update intake_readiness
    def test_sm10_update_readiness(self, mgr):
        from server.models import IntakeReadiness

        session = mgr.create_session("user_001", "opp_acme")
        readiness = IntakeReadiness(deal_stage="present", signals_confirmed=True)
        mgr.update_session(session.session_id, intake_readiness=readiness)
        fetched = mgr.get_session(session.session_id)
        assert fetched.intake_readiness.deal_stage == "present"
        assert fetched.intake_readiness.signals_confirmed is True

    # SM-11: Update session state
    def test_sm11_update_state(self, mgr):
        session = mgr.create_session("user_001", "opp_acme")
        mgr.update_session(session.session_id, state="INTAKE")
        fetched = mgr.get_session(session.session_id)
        assert fetched.state == "INTAKE"

    # SM-12: Read-after-write consistency
    def test_sm12_read_after_write(self, mgr):
        session = mgr.create_session("user_001", "opp_acme")
        mgr.update_session(session.session_id, active_signals=["champion_gone_silent"])
        mgr.update_session(session.session_id, active_signals=["champion_gone_silent", "economic_buyer_disengaged"])
        fetched = mgr.get_session(session.session_id)
        assert len(fetched.active_signals) == 2

    # SM-13: updated_at changes on every write
    def test_sm13_updated_at_changes(self, mgr):
        import time

        session = mgr.create_session("user_001", "opp_acme")
        first_update = mgr.get_session(session.session_id).updated_at
        time.sleep(0.01)
        mgr.update_session(session.session_id, state="INTAKE")
        second_update = mgr.get_session(session.session_id).updated_at
        assert second_update > first_update

    # SM-14: List sessions for a user
    def test_sm14_list_sessions(self, mgr):
        mgr.create_session("user_001", "opp_acme")
        mgr.create_session("user_001", "opp_globex")
        mgr.create_session("user_002", "opp_initech")
        sessions = mgr.list_sessions("user_001")
        assert len(sessions) == 2
        assert all(s.user_id == "user_001" for s in sessions)
