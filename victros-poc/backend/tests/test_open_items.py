"""Tier 1 — Open Items from UAT Round 1 (OI-01 → OI-18).

Covers the four backend-testable items from Richard's Apr 13 UAT notes:

  OI-01 → OI-04  Signal prioritisation  (Item 6)
    Signals returned by the API and used in the engine must be ordered by
    severity (CRITICAL → HIGH → MEDIUM → LOW) so the UI can render the
    most important ones first without doing any sorting itself.

  OI-05 → OI-09  Action context  (Item 4)
    The confirm-patterns and select-action responses currently return action
    keys only. They must return full action objects (key + description +
    ux_text) so the UI can explain each action to the user before they pick.

  OI-10 → OI-13  Pivot stage retention  (Item 5 / UI-UX 3)
    When a user re-enters from MONITORING ("Something Changed"), the session
    already has a deal_snapshot.stage. The confirm step must NOT require the
    caller to re-supply deal_stage — it reads it from the stored snapshot.
    After re-evaluation the session must land at PATTERN_DIAGNOSTICS (not
    skip straight to actions), exactly as a first-pass confirm does.

  OI-14 → OI-18  Intake field tracking in session  (Item 3 / Logic 2)
    The session must persist which of the 23 structured input fields have
    been collected so the UI can show a gap checklist and the API can report
    missing fields. IntakeTracker.to_dict() / from_dict() must round-trip
    through session storage.

Written BEFORE the fixes exist.
"""
import pathlib
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# ═══════════════════════════════════════════════════════════════════════════
# OI-01 → OI-04  Signal Prioritisation
# ═══════════════════════════════════════════════════════════════════════════
class TestSignalPrioritisation:
    @pytest.fixture
    def client(self, tmp_path):
        from server.main import create_app
        from fastapi.testclient import TestClient
        return TestClient(create_app(sessions_dir=tmp_path))

    # OI-01: GET /api/schema/signals returns signals sorted CRITICAL → LOW
    def test_oi01_signals_sorted_by_severity(self, client):
        resp = client.get("/api/schema/signals")
        signals = resp.json()
        severities = [s["severity"] for s in signals]
        ranks = [SEVERITY_ORDER[sev] for sev in severities]
        assert ranks == sorted(ranks), (
            "Signals must be returned sorted CRITICAL → HIGH → MEDIUM → LOW"
        )

    # OI-02: Negative signals (risks) appear before positive signals within each severity tier
    def test_oi02_negative_before_positive_within_tier(self, client):
        resp = client.get("/api/schema/signals")
        signals = resp.json()
        # Within each severity tier, polarity="negative" must come before "positive"
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            tier = [s["polarity"] for s in signals if s["severity"] == sev]
            if not tier:
                continue
            # Once we see a positive, we should not see a negative after it
            seen_positive = False
            for polarity in tier:
                if polarity == "positive":
                    seen_positive = True
                if seen_positive and polarity == "negative":
                    pytest.fail(
                        f"In tier {sev}: negative signal appears after positive signal"
                    )

    # OI-03: Decision engine activate_patterns respects severity ordering in its output
    def test_oi03_engine_activates_by_severity(self):
        from server.decision_engine import DecisionEngine
        from server.schema_store import SchemaStore

        store = SchemaStore(SCHEMA_DIR)
        engine = DecisionEngine(store)
        # Use signals that activate multiple patterns with different severities
        activated = engine.activate_patterns([
            "single_threaded_contact",          # activates singlethreaded_risk (HIGH)
            "problem_not_validated",             # activates weak_problem_definition (CRITICAL)
        ])
        if len(activated) >= 2:
            first_rank = SEVERITY_ORDER.get(activated[0].severity, 99)
            second_rank = SEVERITY_ORDER.get(activated[1].severity, 99)
            assert first_rank <= second_rank, (
                "Engine must return activated patterns ordered CRITICAL first"
            )

    # OI-04: format_pattern_group preserves severity ordering
    def test_oi04_pattern_group_severity_ordering(self):
        from server.pattern_diagnostics import format_pattern_group
        from server.schema_store import SchemaStore

        store = SchemaStore(SCHEMA_DIR)
        # Fetch a CRITICAL and a HIGH pattern and pass them in reverse order
        p_critical = store.get_pattern("weak_problem_definition")   # CRITICAL
        p_high = store.get_pattern("singlethreaded_risk")           # HIGH
        assert p_critical and p_high, "Test patterns must exist in schema"

        group = format_pattern_group([p_high, p_critical])  # intentionally wrong order
        severities = [p["severity"] for p in group["patterns"]]
        ranks = [SEVERITY_ORDER[s] for s in severities]
        assert ranks == sorted(ranks), (
            "format_pattern_group must sort patterns CRITICAL first"
        )


# ═══════════════════════════════════════════════════════════════════════════
# OI-05 → OI-09  Action Context in API Responses
# ═══════════════════════════════════════════════════════════════════════════
class TestActionContext:
    @pytest.fixture
    def client(self, tmp_path):
        from server.main import create_app
        from fastapi.testclient import TestClient
        return TestClient(create_app(sessions_dir=tmp_path))

    @pytest.fixture
    def session_at_action_selection(self, client):
        """Drive session to ACTION_SELECTION through full flow and return (sid, cp_resp)."""
        from tests.conftest import advance_to_pattern_diagnostics
        r = client.post("/api/session/create", json={
            "user_id": "u1", "opportunity_id": "opp1",
        })
        sid = r.json()["session_id"]
        advance_to_pattern_diagnostics(client, sid)
        cp = client.post(f"/api/session/{sid}/confirm-patterns", json={
            "response": "confirm_all",
        })
        cp_data = cp.json()
        # Advance through PRESENTING_DIAGNOSIS → ALIGNMENT_CHECKPOINT → ACTION_SELECTION
        session = client.get(f"/api/session/{sid}").json()
        if session["state"] == "PRESENTING_DIAGNOSIS":
            client.post(f"/api/session/{sid}/confirm-understanding", json={
                "response": "confirm",
            })
        session = client.get(f"/api/session/{sid}").json()
        if session["state"] == "ALIGNMENT_CHECKPOINT":
            r2 = client.post(f"/api/session/{sid}/alignment-checkpoint", json={
                "response": "aligned",
            })
            cp_data = r2.json()
        return sid, cp_data

    # OI-05: confirm-patterns response includes full action objects, not just keys
    def test_oi05_confirm_patterns_returns_full_actions(self, session_at_action_selection):
        _, cp_data = session_at_action_selection
        actions = cp_data.get("representative_actions", [])
        assert len(actions) > 0, "At least one action must be returned"
        first = actions[0]
        assert "action_key" in first, "Action must have action_key"
        assert "ux_text" in first, "Action must have ux_text"
        assert "description" in first, "Action must have description"

    # OI-06: Each returned action has a non-empty ux_text
    def test_oi06_all_actions_have_ux_text(self, session_at_action_selection):
        _, cp_data = session_at_action_selection
        for action in cp_data.get("representative_actions", []):
            assert action.get("ux_text"), f"Action {action.get('action_key')} has empty ux_text"

    # OI-07: select-action response includes the description of the chosen action
    def test_oi07_select_action_returns_action_description(self, client, session_at_action_selection):
        sid, cp_data = session_at_action_selection
        actions = cp_data.get("representative_actions", [])
        if not actions:
            pytest.skip("No actions available")
        action_key = actions[0]["action_key"]
        resp = client.post(f"/api/session/{sid}/select-action", json={
            "action_key": action_key,
        })
        data = resp.json()
        assert "action_description" in data, "select-action must return action_description"
        assert len(data["action_description"]) > 0

    # OI-08: GET /api/schema/representative-actions returns ux_text for all actions
    def test_oi08_schema_actions_have_ux_text(self, client):
        resp = client.get("/api/schema/representative-actions")
        for action in resp.json():
            assert "ux_text" in action

    # OI-09: Actions are grouped by parent_strategy_path in the schema endpoint
    def test_oi09_actions_grouped_by_strategy_path(self, client):
        resp = client.get("/api/schema/representative-actions")
        actions = resp.json()
        sp_keys = {a["parent_strategy_path"] for a in actions}
        assert len(sp_keys) > 1, "Actions must span multiple strategy paths"


# ═══════════════════════════════════════════════════════════════════════════
# OI-10 → OI-13  Pivot Stage Retention
# ═══════════════════════════════════════════════════════════════════════════
class TestPivotStageRetention:
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
            "user_id": "u1", "opportunity_id": "opp1",
        })
        sid = r.json()["session_id"]
        return advance_to_monitoring(client, sid)

    # OI-10: Pivot re-entry from MONITORING transitions session to AWAITING_CONFIRMATION
    def test_oi10_pivot_transitions_to_awaiting(self, client, session_in_monitoring):
        sid = session_in_monitoring
        # "Something Changed" — re-submit new signals
        resp = client.post(f"/api/session/{sid}/input", json={
            "input_type": "button",
            "signals": ["new_stakeholder_appears_late"],
        })
        assert resp.json()["state"] == "AWAITING_CONFIRMATION"

    # OI-11: Pivot confirm does NOT require deal_stage when session already has one
    def test_oi11_pivot_confirm_retains_existing_stage(self, client, session_in_monitoring):
        sid = session_in_monitoring
        client.post(f"/api/session/{sid}/input", json={
            "input_type": "button",
            "signals": ["new_stakeholder_appears_late"],
        })
        # Confirm WITHOUT supplying deal_stage — it should read from stored snapshot
        resp = client.post(f"/api/session/{sid}/confirm", json={
            "response": "confirm",
            # no deal_stage — must use existing deal_snapshot.stage
        })
        assert resp.status_code == 200
        data = resp.json()
        # Must not bounce back to INTAKE asking for stage
        assert data["state"] != "INTAKE", (
            "Pivot confirm must not ask for stage already stored in session"
        )

    # OI-12: After pivot re-evaluation, session lands at PATTERN_DIAGNOSTICS
    def test_oi12_pivot_re_eval_lands_at_pattern_diagnostics(self, client, session_in_monitoring):
        sid = session_in_monitoring
        client.post(f"/api/session/{sid}/input", json={
            "input_type": "button",
            "signals": ["new_stakeholder_appears_late"],
        })
        resp = client.post(f"/api/session/{sid}/confirm", json={
            "response": "confirm",
        })
        assert resp.json()["state"] == "PATTERN_DIAGNOSTICS"

    # OI-13: Pivot preserves previously confirmed signals (merges, not replaces)
    def test_oi13_pivot_merges_signals(self, client, session_in_monitoring):
        sid = session_in_monitoring
        client.post(f"/api/session/{sid}/input", json={
            "input_type": "button",
            "signals": ["new_stakeholder_appears_late"],
        })
        client.post(f"/api/session/{sid}/confirm", json={
            "response": "confirm",
        })
        session = client.get(f"/api/session/{sid}").json()
        active = session["active_signals"]
        # Both the original signal and the new one must be present
        assert "single_threaded_contact" in active
        assert "new_stakeholder_appears_late" in active


# ═══════════════════════════════════════════════════════════════════════════
# OI-14 → OI-18  Intake Field Tracking Persisted in Session
# ═══════════════════════════════════════════════════════════════════════════
class TestIntakeFieldTracking:
    @pytest.fixture
    def client(self, tmp_path):
        from server.main import create_app
        from fastapi.testclient import TestClient
        return TestClient(create_app(sessions_dir=tmp_path))

    # OI-14: POST /api/session/{id}/input with field data stores it in session intake_fields
    def test_oi14_text_input_stores_extracted_fields(self, client):
        from tests.conftest import advance_to_intake
        r = client.post("/api/session/create", json={
            "user_id": "u1", "opportunity_id": "opp1",
        })
        sid = r.json()["session_id"]
        advance_to_intake(client, sid)
        # Submit structured field data directly
        resp = client.post(f"/api/session/{sid}/input", json={
            "input_type": "fields",
            "fields": {"compelling_problem": "No ROI story", "deal_stage": "3_Validation"},
        })
        assert resp.status_code == 200
        session = client.get(f"/api/session/{sid}").json()
        intake_fields = session.get("intake_fields", {})
        # intake_fields is {"fields": {field: value, ...}, "active_signals": [...]}
        fields = intake_fields.get("fields", {})
        assert fields.get("compelling_problem") == "No ROI story"

    # OI-15: GET /api/session/{id} returns intake_fields showing which fields are filled
    def test_oi15_session_exposes_intake_fields(self, client):
        r = client.post("/api/session/create", json={
            "user_id": "u1", "opportunity_id": "opp1",
        })
        sid = r.json()["session_id"]
        session = client.get(f"/api/session/{sid}").json()
        # Fresh session must expose intake_fields (all None initially)
        assert "intake_fields" in session

    # OI-16: GET /api/session/{id}/intake-gaps returns which required fields are missing
    def test_oi16_intake_gaps_endpoint(self, client):
        r = client.post("/api/session/create", json={
            "user_id": "u1", "opportunity_id": "opp1",
        })
        sid = r.json()["session_id"]
        resp = client.get(f"/api/session/{sid}/intake-gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert "required" in data
        assert "deal_stage" in data["required"]
        assert "has_signals" in data

    # OI-17: Intake fields survive a session save/load round-trip
    def test_oi17_intake_fields_persist_across_reload(self, tmp_path):
        from server.session_manager import SessionManager
        from server.intake_tracker import IntakeTracker

        mgr = SessionManager(sessions_dir=tmp_path)
        s = mgr.create_session(user_id="u1", opportunity_id="opp1")

        tracker = IntakeTracker()
        tracker.set_field("compelling_problem", "No ROI story")
        tracker.set_field("deal_stage", "3_Validation")
        tracker.set_signals(["single_threaded_contact"])

        # Persist tracker data into the session
        mgr.update_session(s.session_id, intake_fields=tracker.to_dict())

        # Reload from disk
        reloaded = mgr.get_session(s.session_id)
        tracker2 = IntakeTracker.from_dict(reloaded.intake_fields)

        assert tracker2.get_status()["deal_stage"] == "3_Validation"
        assert tracker2.get_status()["compelling_problem"] == "No ROI story"
        assert tracker2.is_ready() is True

    # OI-18: Confirm endpoint uses stored intake_fields.deal_stage when no deal_stage in request
    def test_oi18_confirm_reads_stage_from_intake_fields(self, client):
        from tests.conftest import advance_to_intake, submit_all_required_fields
        r = client.post("/api/session/create", json={
            "user_id": "u1", "opportunity_id": "opp1",
        })
        sid = r.json()["session_id"]
        advance_to_intake(client, sid)
        # Store all required fields including stage via the fields input
        submit_all_required_fields(client, sid)
        # Submit signals
        client.post(f"/api/session/{sid}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact"],
        })
        # Confirm WITHOUT deal_stage — must read from stored intake_fields
        resp = client.post(f"/api/session/{sid}/confirm", json={
            "response": "confirm",
        })
        assert resp.status_code == 200
        assert resp.json()["state"] == "PATTERN_DIAGNOSTICS"
