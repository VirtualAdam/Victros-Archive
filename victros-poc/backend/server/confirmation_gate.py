"""Confirmation Gate — formats proposals and processes user responses."""
from __future__ import annotations


class ConfirmationGate:
    """Pure logic — no LLM. Formats proposals, validates responses."""

    @staticmethod
    def format_proposal(
        proposed_signals: list[str],
        proposed_deal_attrs: dict,
        remove_signals: list[str] | None = None,
    ) -> dict:
        items = []

        for sig in proposed_signals:
            items.append({"signal": sig, "action": "add"})

        for key, value in proposed_deal_attrs.items():
            items.append({"attribute": key, "value": value, "action": "add"})

        if remove_signals:
            for sig in remove_signals:
                items.append({"signal": sig, "action": "remove"})

        needs_confirmation = len(items) > 0

        return {
            "items": items,
            "needs_confirmation": needs_confirmation,
            "options": ["Yes, that's accurate", "Adjust", "Not correct"],
        }

    @staticmethod
    def process_response(
        response: str,
        proposed_signals: list[str],
        proposed_deal_attrs: dict,
    ) -> dict:
        if response == "confirm":
            return {
                "confirmed": True,
                "signals": proposed_signals,
                "deal_attrs": proposed_deal_attrs,
            }
        elif response == "adjust":
            return {
                "confirmed": False,
                "action": "re_entry",
                "signals": proposed_signals,
                "deal_attrs": proposed_deal_attrs,
            }
        else:  # reject
            return {
                "confirmed": False,
                "action": "restart",
                "signals": [],
                "deal_attrs": {},
            }
