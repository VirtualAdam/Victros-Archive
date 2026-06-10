"""Tier 1 — Confirmation Gate Tests (CG-01 → CG-07).

Written BEFORE confirmation_gate.py exists.
"""
import pytest


class TestConfirmationGate:
    # CG-01: Format proposed signals into confirmation card structure
    def test_cg01_format_signal_proposal(self):
        from server.confirmation_gate import ConfirmationGate

        proposal = ConfirmationGate.format_proposal(
            proposed_signals=["single_threaded_contact", "competition_gaining_mindshare"],
            proposed_deal_attrs={},
        )
        assert "items" in proposal
        assert len(proposal["items"]) == 2
        assert proposal["options"] == ["Yes, that's accurate", "Adjust", "Not correct"]

    # CG-02: User confirms → confirmed=True, signals unchanged
    def test_cg02_confirm(self):
        from server.confirmation_gate import ConfirmationGate

        result = ConfirmationGate.process_response(
            response="confirm",
            proposed_signals=["single_threaded_contact"],
            proposed_deal_attrs={},
        )
        assert result["confirmed"] is True
        assert result["signals"] == ["single_threaded_contact"]

    # CG-03: User rejects → confirmed=False
    def test_cg03_reject(self):
        from server.confirmation_gate import ConfirmationGate

        result = ConfirmationGate.process_response(
            response="reject",
            proposed_signals=["single_threaded_contact"],
            proposed_deal_attrs={},
        )
        assert result["confirmed"] is False

    # CG-04: User adjusts → confirmed=False, marked for re-entry
    def test_cg04_adjust(self):
        from server.confirmation_gate import ConfirmationGate

        result = ConfirmationGate.process_response(
            response="adjust",
            proposed_signals=["single_threaded_contact"],
            proposed_deal_attrs={},
        )
        assert result["confirmed"] is False
        assert result["action"] == "re_entry"

    # CG-05: Empty proposal → no confirmation needed
    def test_cg05_empty_proposal(self):
        from server.confirmation_gate import ConfirmationGate

        proposal = ConfirmationGate.format_proposal(
            proposed_signals=[],
            proposed_deal_attrs={},
        )
        assert proposal["items"] == []
        assert proposal["needs_confirmation"] is False

    # CG-06: Format proposed deal attribute changes
    def test_cg06_format_deal_attrs(self):
        from server.confirmation_gate import ConfirmationGate

        proposal = ConfirmationGate.format_proposal(
            proposed_signals=[],
            proposed_deal_attrs={"stage": "3_Validation", "amount": 1200000},
        )
        assert len(proposal["items"]) == 2
        assert proposal["needs_confirmation"] is True

    # CG-07: Format Schema Delta from Pivot (add + remove signals)
    def test_cg07_format_schema_delta(self):
        from server.confirmation_gate import ConfirmationGate

        proposal = ConfirmationGate.format_proposal(
            proposed_signals=["champion_actively_selling"],
            proposed_deal_attrs={},
            remove_signals=["champion_gone_silent"],
        )
        assert proposal["needs_confirmation"] is True
        # Should have items for both additions and removals
        add_items = [i for i in proposal["items"] if i["action"] == "add"]
        remove_items = [i for i in proposal["items"] if i["action"] == "remove"]
        assert len(add_items) == 1
        assert len(remove_items) == 1
