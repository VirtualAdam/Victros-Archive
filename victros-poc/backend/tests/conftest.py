"""Shared fixtures for all Victros tests."""
import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
FIXTURES_DIR = pathlib.Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def schema_dir():
    """Path to the canonical schema JSON files."""
    return SCHEMA_DIR


@pytest.fixture
def fixtures_dir():
    """Path to test fixture files."""
    return FIXTURES_DIR


# ---------------------------------------------------------------------------
# Shared test helpers for the new state machine flow
# ---------------------------------------------------------------------------

def advance_to_intake(client, session_id: str) -> None:
    """Drive a session from INTENT_CAPTURE through SITUATION_VALIDATION to INTAKE.

    After create_session, sessions start in INTENT_CAPTURE.
    This helper submits intent text, confirms the situation, and lands in INTAKE.
    """
    # S2: Submit intent text → SITUATION_VALIDATION
    client.post(f"/api/session/{session_id}/input", json={
        "input_type": "text",
        "content": "I need help closing this deal",
    })
    # S3: Confirm situation → INTAKE
    client.post(f"/api/session/{session_id}/confirm", json={
        "response": "confirm",
    })


def submit_all_required_fields(client, session_id: str, deal_stage: str = "3_Validation") -> None:
    """Submit all 6 required intake fields."""
    client.post(f"/api/session/{session_id}/input", json={
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


def advance_to_awaiting_confirmation(
    client, session_id: str, signals: list[str] | None = None, deal_stage: str = "3_Validation"
) -> dict:
    """Drive a session from INTENT_CAPTURE all the way to AWAITING_CONFIRMATION.

    Returns the response from the signal submission.
    """
    advance_to_intake(client, session_id)
    submit_all_required_fields(client, session_id, deal_stage)
    sigs = signals or ["single_threaded_contact"]
    resp = client.post(f"/api/session/{session_id}/input", json={
        "input_type": "button",
        "signals": sigs,
    })
    return resp.json()


def advance_to_pattern_diagnostics(
    client, session_id: str, signals: list[str] | None = None, deal_stage: str = "3_Validation"
) -> dict:
    """Drive a session all the way to PATTERN_DIAGNOSTICS.

    Returns the confirm response.
    """
    advance_to_awaiting_confirmation(client, session_id, signals, deal_stage)
    resp = client.post(f"/api/session/{session_id}/confirm", json={
        "response": "confirm",
        "deal_stage": deal_stage,
    })
    return resp.json()


def advance_to_monitoring(client, session_id: str, signals: list[str] | None = None, deal_stage: str = "3_Validation") -> str:
    """Drive a session all the way to MONITORING. Returns session_id."""
    advance_to_pattern_diagnostics(client, session_id, signals=signals, deal_stage=deal_stage)
    cp = client.post(f"/api/session/{session_id}/confirm-patterns", json={
        "response": "confirm_all",
    })
    cp_data = cp.json()
    state = cp_data.get("state")

    # PRESENTING_DIAGNOSIS → confirm understanding → ALIGNMENT_CHECKPOINT
    if state == "PRESENTING_DIAGNOSIS":
        r = client.post(f"/api/session/{session_id}/confirm-understanding", json={
            "response": "confirm",
        })
        state = r.json().get("state")

    # ALIGNMENT_CHECKPOINT → aligned → ACTION_SELECTION (or DUAL_PATTERN_TRADEOFF)
    if state == "ALIGNMENT_CHECKPOINT":
        r = client.post(f"/api/session/{session_id}/alignment-checkpoint", json={
            "response": "aligned",
        })
        cp_data = r.json()
        state = cp_data.get("state")

    # DUAL_PATTERN_TRADEOFF → focus → ACTION_SELECTION
    if state == "DUAL_PATTERN_TRADEOFF":
        r = client.post(f"/api/session/{session_id}/dual-pattern", json={
            "choice": "focus",
        })
        cp_data = r.json()
        state = cp_data.get("state")

    # ACTION_SELECTION → select action → MONITORING
    if state == "ACTION_SELECTION":
        actions = cp_data.get("representative_actions", [])
        if not actions:
            # Fetch actions from session
            session = client.get(f"/api/session/{session_id}").json()
            sp_key = session.get("selected_strategy_path")
            if sp_key:
                all_actions = client.get("/api/schema/representative-actions").json()
                actions = [a for a in all_actions if a.get("parent_strategy_path") == sp_key]
        if actions:
            a = actions[0]
            action_key = a["action_key"] if isinstance(a, dict) else a
            client.post(f"/api/session/{session_id}/select-action", json={
                "action_key": action_key,
            })
    return session_id
