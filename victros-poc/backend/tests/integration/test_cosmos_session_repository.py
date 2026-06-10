"""Integration tests — CosmosSessionRepository (IT-01 → IT-14).

These mirror the SM-01..SM-14 unit tests but run against the real
Cosmos DB emulator. They are skipped automatically when the emulator
is not running; see conftest.py for details.

Run with:
  docker compose up cosmosdb -d
  pytest -m integration
"""
import time
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
class TestCosmosSessionRepositoryCRUD:

    # IT-01: Create a new session
    def test_it01_create_session(self, cosmos_repo):
        session = cosmos_repo.create_session(user_id="it_user_001", opportunity_id="it_opp_acme")
        assert session.session_id
        assert session.user_id == "it_user_001"
        assert session.opportunity_id == "it_opp_acme"
        assert session.state == "NEW_SESSION"
        assert all(v == "WEAK" for v in session.lever_states.values())
        assert session.intake_readiness.deal_stage == "missing"

    # IT-02: Get session by ID
    def test_it02_get_session(self, cosmos_repo):
        created = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        fetched = cosmos_repo.get_session(created.session_id)
        assert fetched is not None
        assert fetched.session_id == created.session_id

    # IT-03: Get non-existent session returns None
    def test_it03_get_nonexistent(self, cosmos_repo):
        result = cosmos_repo.get_session("does-not-exist-at-all")
        assert result is None

    # IT-04: Update active_signals round-trips correctly
    def test_it04_update_signals(self, cosmos_repo):
        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        cosmos_repo.update_session(session.session_id, active_signals=["single_threaded_contact"])
        fetched = cosmos_repo.get_session(session.session_id)
        assert fetched.active_signals == ["single_threaded_contact"]

    # IT-05: Update deal_snapshot
    def test_it05_update_deal_snapshot(self, cosmos_repo):
        from server.models import DealSnapshot

        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        snap = DealSnapshot(stage="3_Validation", amount=1200000)
        cosmos_repo.update_session(session.session_id, deal_snapshot=snap)
        fetched = cosmos_repo.get_session(session.session_id)
        assert fetched.deal_snapshot.stage == "3_Validation"
        assert fetched.deal_snapshot.amount == 1200000

    # IT-06: Update lever_states
    def test_it06_update_lever_states(self, cosmos_repo):
        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        new_levers = session.lever_states.copy()
        new_levers["champion_strength"] = "CONNECTED"
        cosmos_repo.update_session(session.session_id, lever_states=new_levers)
        fetched = cosmos_repo.get_session(session.session_id)
        assert fetched.lever_states["champion_strength"] == "CONNECTED"

    # IT-07: Update active_patterns
    def test_it07_update_patterns(self, cosmos_repo):
        from server.models import ActivePatterns

        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        patterns = ActivePatterns(
            primary="single_threaded_risk",
            secondary=["competitive_displacement"],
        )
        cosmos_repo.update_session(session.session_id, active_patterns=patterns)
        fetched = cosmos_repo.get_session(session.session_id)
        assert fetched.active_patterns.primary == "single_threaded_risk"
        assert "competitive_displacement" in fetched.active_patterns.secondary

    # IT-08: Update selected_strategy_path
    def test_it08_update_strategy_path(self, cosmos_repo):
        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        cosmos_repo.update_session(
            session.session_id, selected_strategy_path="selling_to_consensus"
        )
        fetched = cosmos_repo.get_session(session.session_id)
        assert fetched.selected_strategy_path == "selling_to_consensus"

    # IT-09: Append to interaction_history
    def test_it09_append_history(self, cosmos_repo):
        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        entry = {"type": "user_input", "content": "integration test message"}
        cosmos_repo.append_history(session.session_id, entry)
        fetched = cosmos_repo.get_session(session.session_id)
        assert len(fetched.interaction_history) == 1
        assert fetched.interaction_history[0]["content"] == "integration test message"

    # IT-10: Update intake_readiness
    def test_it10_update_readiness(self, cosmos_repo):
        from server.models import IntakeReadiness

        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        readiness = IntakeReadiness(deal_stage="present", signals_confirmed=True)
        cosmos_repo.update_session(session.session_id, intake_readiness=readiness)
        fetched = cosmos_repo.get_session(session.session_id)
        assert fetched.intake_readiness.deal_stage == "present"
        assert fetched.intake_readiness.signals_confirmed is True

    # IT-11: Update session state
    def test_it11_update_state(self, cosmos_repo):
        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        cosmos_repo.update_session(session.session_id, state="INTAKE")
        fetched = cosmos_repo.get_session(session.session_id)
        assert fetched.state == "INTAKE"

    # IT-12: Read-after-write consistency — last write wins
    def test_it12_read_after_write(self, cosmos_repo):
        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        cosmos_repo.update_session(
            session.session_id, active_signals=["champion_gone_silent"]
        )
        cosmos_repo.update_session(
            session.session_id,
            active_signals=["champion_gone_silent", "economic_buyer_disengaged"],
        )
        fetched = cosmos_repo.get_session(session.session_id)
        assert len(fetched.active_signals) == 2

    # IT-13: updated_at advances on every write
    def test_it13_updated_at_changes(self, cosmos_repo):
        session = cosmos_repo.create_session("it_user_001", "it_opp_acme")
        first_update = cosmos_repo.get_session(session.session_id).updated_at
        time.sleep(0.05)  # Cosmos round-trip may reuse sub-ms timestamps
        cosmos_repo.update_session(session.session_id, state="INTAKE")
        second_update = cosmos_repo.get_session(session.session_id).updated_at
        assert second_update > first_update

    # IT-14: list_sessions returns only the correct user's sessions
    def test_it14_list_sessions(self, cosmos_repo):
        import uuid as _uuid

        # Use unique user IDs per test run to avoid cross-test pollution
        uid_a = f"list_test_user_a_{_uuid.uuid4().hex[:8]}"
        uid_b = f"list_test_user_b_{_uuid.uuid4().hex[:8]}"

        cosmos_repo.create_session(uid_a, "it_opp_acme")
        cosmos_repo.create_session(uid_a, "it_opp_globex")
        cosmos_repo.create_session(uid_b, "it_opp_initech")

        sessions_a = cosmos_repo.list_sessions(uid_a)
        assert len(sessions_a) == 2
        assert all(s.user_id == uid_a for s in sessions_a)

        sessions_b = cosmos_repo.list_sessions(uid_b)
        assert len(sessions_b) == 1
