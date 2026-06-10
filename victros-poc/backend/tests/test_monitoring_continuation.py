"""Tier TDD — Monitoring Continuation Tests (MC-01 → MC-08).

Phase 5: After reaching MONITORING via action selection, the user is presented with
continuation options. This includes "address_next_issue" which re-runs pattern
prioritization excluding the current primary pattern, and "exit_for_now" which
saves session state as SESSION_PAUSED for later resumption.

Written BEFORE the continuation options and SESSION_PAUSED state exist.
All tests are xfail until the endpoints and state transitions are implemented.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
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
        "user_id": "mc_user",
        "opportunity_id": "mc_opp",
    })
    assert resp.status_code == 201
    return resp.json()["session_id"]


@pytest.fixture
def session_in_monitoring(client, session_id):
    """Drive a session all the way to MONITORING. Returns session_id.

    Uses two signals that activate different patterns so address_next_issue
    can find a second pattern after excluding the first.
    """
    return advance_to_monitoring(
        client, session_id,
        signals=["single_threaded_contact", "problem_not_validated"],
    )


def _get_session(client: TestClient, session_id: str) -> dict:
    resp = client.get(f"/api/session/{session_id}")
    assert resp.status_code == 200
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# MC-01: Four options returned at MONITORING
# ═══════════════════════════════════════════════════════════════════════════


class TestMC01_FourOptionsReturned:
    """After reaching MONITORING, response includes all 4 continuation options."""

    def test_mc01_four_options_returned(self, client, session_in_monitoring):
        sid = session_in_monitoring
        session = _get_session(client, sid)
        assert session["state"] == "MONITORING"

        # The monitoring state should present continuation options
        options = session.get("continuation_options", [])
        expected_options = {"continue", "re_evaluate", "address_next_issue", "exit_for_now"}
        actual_options = {opt if isinstance(opt, str) else opt.get("key") for opt in options}
        assert expected_options.issubset(actual_options), (
            f"Expected options {expected_options}, got {actual_options}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# MC-02: address_next_issue excludes current pattern
# ═══════════════════════════════════════════════════════════════════════════


class TestMC02_AddressNextIssueExcludesCurrentPattern:
    """Sending 'address_next_issue' re-runs pattern prioritization excluding current."""

    def test_mc02_address_next_issue_excludes_current_pattern(self, client, session_in_monitoring):
        sid = session_in_monitoring
        session = _get_session(client, sid)
        current_pattern = session.get("primary_pattern") or session.get("selected_strategy_path")
        assert current_pattern is not None, "Session should have a primary pattern"

        r = client.post(f"/api/session/{sid}/monitoring-action", json={
            "action": "address_next_issue",
        })
        assert r.status_code == 200
        data = r.json()

        # The new primary pattern should differ from the previous one
        new_pattern = data.get("primary_pattern") or data.get("selected_strategy_path")
        assert new_pattern != current_pattern, (
            f"New pattern should differ from current ({current_pattern})"
        )


# ═══════════════════════════════════════════════════════════════════════════
# MC-03: address_next_issue selects new strategy
# ═══════════════════════════════════════════════════════════════════════════


class TestMC03_AddressNextIssueSelectsNewStrategy:
    """After address_next_issue, a different pattern becomes primary with its own strategy."""

    def test_mc03_address_next_issue_selects_new_strategy(self, client, session_in_monitoring):
        sid = session_in_monitoring
        session_before = _get_session(client, sid)
        old_strategy = session_before.get("selected_strategy_path")

        r = client.post(f"/api/session/{sid}/monitoring-action", json={
            "action": "address_next_issue",
        })
        assert r.status_code == 200

        # After re-evaluation completes and reaches PRESENTING_DIAGNOSIS,
        # the new strategy path should differ
        session_after = _get_session(client, sid)
        new_strategy = session_after.get("selected_strategy_path")
        # A new pattern means a new strategy path
        if old_strategy and new_strategy:
            assert new_strategy != old_strategy, (
                "address_next_issue should produce a different strategy path"
            )


# ═══════════════════════════════════════════════════════════════════════════
# MC-04: address_next_issue transitions correctly
# ═══════════════════════════════════════════════════════════════════════════


class TestMC04_AddressNextIssueTransitionsCorrectly:
    """MONITORING → ALIGNMENT_CHECKPOINT (with new pattern after re-evaluation)."""

    def test_mc04_address_next_issue_transitions_correctly(self, client, session_in_monitoring):
        sid = session_in_monitoring
        assert _get_session(client, sid)["state"] == "MONITORING"

        r = client.post(f"/api/session/{sid}/monitoring-action", json={
            "action": "address_next_issue",
        })
        assert r.status_code == 200
        data = r.json()

        # The endpoint re-evaluates with excluded patterns and goes to checkpoint
        assert data["state"] in ("RE_EVALUATING", "ALIGNMENT_CHECKPOINT"), (
            f"Expected RE_EVALUATING or ALIGNMENT_CHECKPOINT, got {data['state']}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# MC-05: exit_for_now saves state
# ═══════════════════════════════════════════════════════════════════════════


class TestMC05_ExitForNowSavesState:
    """Sending 'exit_for_now' from MONITORING saves all session state."""

    def test_mc05_exit_for_now_saves_state(self, client, session_in_monitoring):
        sid = session_in_monitoring
        session_before = _get_session(client, sid)
        strategy_before = session_before.get("selected_strategy_path")

        r = client.post(f"/api/session/{sid}/monitoring-action", json={
            "action": "exit_for_now",
        })
        assert r.status_code == 200

        # Session should still be retrievable with all state preserved
        session_after = _get_session(client, sid)
        assert session_after.get("selected_strategy_path") == strategy_before, (
            "Strategy path should be preserved after exit_for_now"
        )
        # Intake fields and pattern data should also persist
        assert session_after.get("intake_fields") is not None or session_after.get("fields") is not None


# ═══════════════════════════════════════════════════════════════════════════
# MC-06: exit_for_now sets SESSION_PAUSED state
# ═══════════════════════════════════════════════════════════════════════════


class TestMC06_ExitForNowSetsPausedState:
    """After exit_for_now, session state = SESSION_PAUSED."""

    def test_mc06_exit_for_now_sets_paused_state(self, client, session_in_monitoring):
        sid = session_in_monitoring

        r = client.post(f"/api/session/{sid}/monitoring-action", json={
            "action": "exit_for_now",
        })
        assert r.status_code == 200

        session = _get_session(client, sid)
        assert session["state"] == "SESSION_PAUSED", (
            f"Expected SESSION_PAUSED after exit_for_now, got {session['state']}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# MC-07: Paused session is resumable
# ═══════════════════════════════════════════════════════════════════════════


class TestMC07_PausedSessionResumable:
    """A SESSION_PAUSED session can be resumed and continues from where it left off."""

    def test_mc07_paused_session_resumable(self, client, session_in_monitoring):
        sid = session_in_monitoring

        # Pause the session
        r = client.post(f"/api/session/{sid}/monitoring-action", json={
            "action": "exit_for_now",
        })
        assert r.status_code == 200
        assert _get_session(client, sid)["state"] == "SESSION_PAUSED"

        # Resume the session
        r = client.post(f"/api/session/{sid}/resume", json={})
        assert r.status_code == 200
        data = r.json()

        # Should return to MONITORING with all state intact
        assert data["state"] == "MONITORING", (
            f"Resumed session should be in MONITORING, got {data['state']}"
        )
        assert data.get("selected_strategy_path") is not None, (
            "Resumed session should retain its strategy path"
        )


# ═══════════════════════════════════════════════════════════════════════════
# MC-08: No next pattern available
# ═══════════════════════════════════════════════════════════════════════════


class TestMC08_NoNextPatternAvailable:
    """If all patterns addressed, address_next_issue returns graceful message."""

    def test_mc08_no_next_pattern_available(self, client, session_in_monitoring):
        sid = session_in_monitoring

        # Exhaust patterns by repeatedly addressing next issue
        # (In practice, most sessions have a limited number of detected patterns.)
        max_iterations = 10
        for _ in range(max_iterations):
            r = client.post(f"/api/session/{sid}/monitoring-action", json={
                "action": "address_next_issue",
            })
            if r.status_code != 200:
                break
            data = r.json()
            # If no more patterns, should get a graceful response
            if data.get("no_more_patterns") or data.get("message"):
                assert "no_more_patterns" in data or "all" in data.get("message", "").lower(), (
                    "Should indicate no more patterns are available"
                )
                return

            # If we got a new pattern, drive it through to monitoring again
            state = data.get("state", "")
            if state == "ALIGNMENT_CHECKPOINT":
                # Advance through checkpoint and action selection back to monitoring
                client.post(f"/api/session/{sid}/alignment-checkpoint", json={
                    "response": "aligned",
                })
                session = _get_session(client, sid)
                if session["state"] == "ACTION_SELECTION":
                    sp_key = session.get("selected_strategy_path")
                    if sp_key:
                        all_actions = client.get("/api/schema/representative-actions").json()
                        actions = [a for a in all_actions if a.get("parent_strategy_path") == sp_key]
                        if actions:
                            action_key = actions[0]["action_key"]
                            client.post(f"/api/session/{sid}/select-action", json={
                                "action_key": action_key,
                            })

        # If we got here, the last call should have indicated no patterns
        final = _get_session(client, sid)
        r = client.post(f"/api/session/{sid}/monitoring-action", json={
            "action": "address_next_issue",
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("no_more_patterns") is True or "no" in data.get("message", "").lower(), (
            "Should gracefully handle exhausted patterns"
        )
