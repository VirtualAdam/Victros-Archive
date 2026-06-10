"""Tier 1 — Monitoring & Progress Layer Tests (MON-01 → MON-13).

Layer 7 from the system-flow spec: once an action is selected the deal enters
MONITORING. The system tracks progress using the rich fields on the selected
StrategyPath:
  - positive_progress_signals: indicators the deal is on track
  - negative_progress_signals: indicators the deal is at risk
  - exit_lever_state: condition string that, when met, means the path is complete
  - exit_outcome: the win condition description
  - transition_signals: signal names that should trigger RE_EVALUATING

Written BEFORE the monitoring module exists.
"""
import pathlib
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"

# Use the first strategy path as a concrete test subject.
# Qualify_CaseForChange has well-populated monitoring fields.
TEST_STRATEGY_PATH_KEY = "Qualify_CaseForChange"


@pytest.fixture
def schema_store():
    from server.schema_store import SchemaStore

    return SchemaStore(SCHEMA_DIR)


@pytest.fixture
def strategy_path(schema_store):
    """Return the Qualify_CaseForChange strategy path for testing."""
    return schema_store.get_strategy_path(TEST_STRATEGY_PATH_KEY)


# ═══════════════════════════════════════════════════════════════════════════
# State Machine Transitions
# ═══════════════════════════════════════════════════════════════════════════
class TestMonitoringTransitions:
    # MON-01: MONITORING → RE_EVALUATING is a valid transition
    def test_mon01_monitoring_to_reevaluating(self):
        from server.state_machine import validate_transition

        assert validate_transition("MONITORING", "RE_EVALUATING") is True

    # MON-02: RE_EVALUATING → SESSION_COMPLETE is a valid transition (exit detected)
    def test_mon02_reevaluating_to_complete(self):
        from server.state_machine import validate_transition

        assert validate_transition("RE_EVALUATING", "SESSION_COMPLETE") is True

    # MON-03: MONITORING → SESSION_COMPLETE is a valid direct transition
    def test_mon03_monitoring_can_go_to_complete(self):
        from server.state_machine import validate_transition

        assert validate_transition("MONITORING", "SESSION_COMPLETE") is True


# ═══════════════════════════════════════════════════════════════════════════
# Strategy Path Monitoring Fields — Schema Accessibility
# ═══════════════════════════════════════════════════════════════════════════
class TestStrategyPathMonitoringFields:
    # MON-04: Selected strategy path has non-empty positive_progress_signals
    def test_mon04_positive_signals_present(self, strategy_path):
        assert len(strategy_path.positive_progress_signals) > 0

    # MON-05: Selected strategy path has non-empty negative_progress_signals
    def test_mon05_negative_signals_present(self, strategy_path):
        assert len(strategy_path.negative_progress_signals) > 0

    # MON-06: Selected strategy path has a non-empty exit_lever_state
    def test_mon06_exit_lever_state_present(self, strategy_path):
        assert len(strategy_path.exit_lever_state) > 0

    # MON-07: Selected strategy path has a non-empty exit_outcome
    def test_mon07_exit_outcome_present(self, strategy_path):
        assert len(strategy_path.exit_outcome) > 0

    # MON-08: Selected strategy path has non-empty transition_signals
    def test_mon08_transition_signals_present(self, strategy_path):
        assert len(strategy_path.transition_signals) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Progress Evaluator — Unit Tests
# ═══════════════════════════════════════════════════════════════════════════
class TestProgressEvaluator:
    # MON-09: Positive progress input → evaluator returns "on_track"
    def test_mon09_positive_input_returns_on_track(self, strategy_path):
        from server.progress_evaluator import evaluate_progress

        # Use actual text matching one of the positive signals
        positive_text = strategy_path.positive_progress_signals[0]
        result = evaluate_progress(
            strategy_path=strategy_path,
            update_text=positive_text,
        )
        assert result["status"] == "on_track"
        assert len(result["matched_positive"]) > 0

    # MON-10: Negative progress input → evaluator returns "at_risk"
    def test_mon10_negative_input_returns_at_risk(self, strategy_path):
        from server.progress_evaluator import evaluate_progress

        negative_text = strategy_path.negative_progress_signals[0]
        result = evaluate_progress(
            strategy_path=strategy_path,
            update_text=negative_text,
        )
        assert result["status"] == "at_risk"
        assert len(result["matched_negative"]) > 0

    # MON-11: Neutral update with no signal matches → evaluator returns "neutral"
    def test_mon11_neutral_update_returns_neutral(self, strategy_path):
        from server.progress_evaluator import evaluate_progress

        result = evaluate_progress(
            strategy_path=strategy_path,
            update_text="Had a call, nothing notable to report.",
        )
        assert result["status"] == "neutral"

    # MON-12: Exit condition met → evaluator includes exit_detected=True
    def test_mon12_exit_condition_detection(self, strategy_path):
        from server.progress_evaluator import evaluate_progress

        # Use the exit_outcome text to trigger exit detection
        result = evaluate_progress(
            strategy_path=strategy_path,
            update_text=strategy_path.exit_outcome,
        )
        assert result["exit_detected"] is True

    # MON-13: Transition signal in update → evaluator includes transition_triggered=True
    def test_mon13_transition_signal_detection(self, strategy_path):
        from server.progress_evaluator import evaluate_progress

        # Use the first transition signal to trigger re-evaluation
        transition_text = strategy_path.transition_signals[0]
        result = evaluate_progress(
            strategy_path=strategy_path,
            update_text=transition_text,
        )
        assert result["transition_triggered"] is True


# ═══════════════════════════════════════════════════════════════════════════
# API-Level Monitoring Flow
# ═══════════════════════════════════════════════════════════════════════════
class TestMonitoringAPI:
    @pytest.fixture
    def client(self, tmp_path):
        from server.main import create_app
        from fastapi.testclient import TestClient

        return TestClient(create_app(sessions_dir=tmp_path))

    @pytest.fixture
    def session_in_monitoring(self, client):
        """Drive a session all the way through to MONITORING state."""
        from tests.conftest import advance_to_monitoring
        resp = client.post("/api/session/create", json={
            "user_id": "user_001",
            "opportunity_id": "opp_acme",
        })
        sid = resp.json()["session_id"]
        return advance_to_monitoring(client, sid)

    # MON-14: Session in MONITORING has a selected_strategy_path set
    def test_mon14_monitoring_has_strategy_path(self, client, session_in_monitoring):
        sid = session_in_monitoring
        state = client.get(f"/api/session/{sid}").json()
        assert state["state"] == "MONITORING"
        assert state["selected_strategy_path"] is not None

    # MON-15: POST /api/session/{id}/progress accepts a progress update
    def test_mon15_progress_endpoint_accepts_update(self, client, session_in_monitoring):
        sid = session_in_monitoring
        resp = client.post(f"/api/session/{sid}/progress", json={
            "update_text": "Had a strong call with the champion.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data  # "on_track" | "at_risk" | "neutral"
