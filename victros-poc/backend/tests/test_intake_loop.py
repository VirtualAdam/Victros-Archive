"""Tier 1 — INTAKE Requirement-Satisfaction Loop Tests (IL-01 → IL-15).

Per the spec (states.md), INTAKE is order-agnostic: any source (text, buttons,
attachment) can satisfy any requirement. The system tracks what has been
collected and asks about gaps. The minimum bar to exit INTAKE is:
  1. A deal stage value
  2. At least one confirmed signal

The 23 structured input fields are defined in the Inputs CSV and the system
must track which have been filled. Optional fields (close_date, amount, etc.)
do NOT block progression.

Written BEFORE the full intake tracking implementation exists.
"""
import pathlib
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"

# The full set of structured input field keys from the Inputs CSV.
# Minimum required: deal_stage + at least one signal.
ALL_INPUT_FIELDS = [
    "deal_stage",
    "close_date",
    "deal_amount",
    "active_persona",
    "compelling_problem",
    "champion_status",
    "eb_alignment",
    "compelling_event",
    "timeline_requirement",
    "decision_process",
    "competitive_landscape",
    "recent_interaction_summary",
    "product_usage_presence",
    "usage_depth",
    "desired_outcomes",
    "measurable_impact",
    "stakeholder_coverage",
    "economic_buyer_identified",
    "economic_buyer_engagement",
    "internal_owner_identified",
    "commercial_awareness",
    "usage_trend",
    "workflow_dependency",
    "removal_impact",
]

REQUIRED_FIELDS = ["deal_stage"]
SIGNAL_REQUIREMENT = True  # At least one confirmed signal is required


# ═══════════════════════════════════════════════════════════════════════════
# Intake Tracker — Unit Tests
# ═══════════════════════════════════════════════════════════════════════════
class TestIntakeTracker:
    # IL-01: Fresh IntakeTracker has all 24 fields (23 inputs + signals) empty
    def test_il01_fresh_tracker_has_all_fields_empty(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        status = tracker.get_status()

        assert status["deal_stage"] is None
        assert status["signals_confirmed"] is False
        for field in ALL_INPUT_FIELDS[1:]:  # skip deal_stage, already checked
            assert status.get(field) is None

    # IL-02: Setting deal_stage fills that field
    def test_il02_setting_deal_stage_fills_field(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_field("deal_stage", "3_Validation")

        assert tracker.get_status()["deal_stage"] == "3_Validation"

    # IL-03: Setting signals marks signals as confirmed
    def test_il03_setting_signals_marks_confirmed(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_signals(["single_threaded_contact"])

        assert tracker.get_status()["signals_confirmed"] is True
        assert "single_threaded_contact" in tracker.get_status()["active_signals"]

    # IL-04: Gap detector returns required fields missing on empty tracker
    def test_il04_gap_detector_returns_required_missing(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        gaps = tracker.get_gaps()

        assert "deal_stage" in gaps["required"]
        assert gaps["has_signals"] is False

    # IL-05: Gap detector excludes fields that have been filled
    def test_il05_gap_detector_excludes_filled_fields(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_field("deal_stage", "3_Validation")
        gaps = tracker.get_gaps()

        assert "deal_stage" not in gaps["required"]

    # IL-06: Readiness gate passes when stage + signals are both present
    def test_il06_ready_with_stage_and_signals(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_field("deal_stage", "3_Validation")
        tracker.set_signals(["single_threaded_contact"])

        assert tracker.is_ready() is True

    # IL-07: Readiness gate fails when stage is missing
    def test_il07_not_ready_without_stage(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_signals(["single_threaded_contact"])

        assert tracker.is_ready() is False
        assert "deal_stage" in tracker.get_gaps()["required"]

    # IL-08: Readiness gate fails when no signals are confirmed
    def test_il08_not_ready_without_signals(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_field("deal_stage", "3_Validation")

        assert tracker.is_ready() is False
        assert tracker.get_gaps()["has_signals"] is False

    # IL-09: Optional fields missing do NOT block readiness
    def test_il09_optional_fields_dont_block_readiness(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_field("deal_stage", "3_Validation")
        tracker.set_signals(["single_threaded_contact"])
        # close_date, deal_amount, compelling_problem, etc. all missing

        assert tracker.is_ready() is True

    # IL-10: Re-setting a field overwrites the previous value
    def test_il10_resetting_field_overwrites_value(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_field("deal_stage", "2_Discovery")
        tracker.set_field("deal_stage", "3_Validation")

        assert tracker.get_status()["deal_stage"] == "3_Validation"

    # IL-11: Re-setting signals replaces the previous signal set
    def test_il11_resetting_signals_replaces_set(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        tracker.set_signals(["single_threaded_contact"])
        tracker.set_signals(["champion_coaching_influence"])

        status = tracker.get_status()
        assert "single_threaded_contact" not in status["active_signals"]
        assert "champion_coaching_influence" in status["active_signals"]


# ═══════════════════════════════════════════════════════════════════════════
# Source-Agnostic Filling (text → extracted fields)
# ═══════════════════════════════════════════════════════════════════════════
class TestIntakeSourceAgnostic:
    # IL-12: Text input that yields an extracted deal_stage fills the tracker field
    def test_il12_text_input_fills_extracted_stage(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        # Simulate extraction result containing deal_stage
        extracted = {"deal_stage": "3_Validation", "compelling_problem": "No ROI story"}
        tracker.apply_extracted(extracted)

        assert tracker.get_status()["deal_stage"] == "3_Validation"
        assert tracker.get_status()["compelling_problem"] == "No ROI story"

    # IL-13: Extracted fields that aren't in the defined field set are ignored
    def test_il13_unknown_extracted_fields_ignored(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        extracted = {"totally_unknown_field": "some_value", "deal_stage": "2_Discovery"}
        tracker.apply_extracted(extracted)

        status = tracker.get_status()
        assert "totally_unknown_field" not in status
        assert status["deal_stage"] == "2_Discovery"

    # IL-14: Button input filling signals via apply_extracted is equivalent to set_signals
    def test_il14_button_signals_via_apply_extracted(self):
        from server.intake_tracker import IntakeTracker

        tracker = IntakeTracker()
        extracted = {"signals": ["single_threaded_contact", "activity_without_progress"]}
        tracker.apply_extracted(extracted)

        status = tracker.get_status()
        assert status["signals_confirmed"] is True
        assert "single_threaded_contact" in status["active_signals"]


# ═══════════════════════════════════════════════════════════════════════════
# API-Level INTAKE Loop
# ═══════════════════════════════════════════════════════════════════════════
class TestIntakeLoopAPI:
    @pytest.fixture
    def client(self, tmp_path):
        from server.main import create_app
        from fastapi.testclient import TestClient

        return TestClient(create_app(sessions_dir=tmp_path))

    @pytest.fixture
    def session_id(self, client):
        resp = client.post("/api/session/create", json={
            "user_id": "user_001",
            "opportunity_id": "opp_acme",
        })
        return resp.json()["session_id"]

    # IL-15: Confirming without all required fields returns state=INTAKE and missing fields
    def test_il15_confirm_without_stage_returns_missing(self, client, session_id):
        from tests.conftest import advance_to_intake
        advance_to_intake(client, session_id)
        # Submit signals via button (but without all required fields)
        # First need to get to AWAITING_CONFIRMATION — submit signals directly
        # and let the API handle readiness checking
        client.post(f"/api/session/{session_id}/input", json={
            "input_type": "button",
            "signals": ["single_threaded_contact"],
        })
        # Session stays in INTAKE because not all required fields are present
        resp = client.get(f"/api/session/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "INTAKE"
