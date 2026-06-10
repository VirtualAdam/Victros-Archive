"""IntakeTracker — requirement-satisfaction loop for the INTAKE state.

Tracks which structured input fields have been collected for a deal.
The minimum bar to exit INTAKE is: deal_stage + at least one confirmed signal.
All other fields are optional but captured when provided.

Source-agnostic: text extraction, button selection, and attachments all feed
into the same tracker via apply_extracted(). The caller is responsible for
normalising the input source into a dict before calling apply_extracted().
"""
from __future__ import annotations

# The full set of structured input field keys.
# Signals are tracked separately via set_signals() / the "signals" key
# in apply_extracted(), not as individual fields here.
INPUT_FIELDS = frozenset([
    "deal_stage",
    "offering_type",
    "offering_usage",
    "usage_depth",
    "deal_amount",
    "deal_close_date",
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
])

REQUIRED_FIELDS = frozenset(["deal_stage"])


class IntakeTracker:
    """Tracks which intake fields have been filled for a single session."""

    def __init__(self) -> None:
        # None means not yet collected
        self._fields: dict[str, str | None] = {k: None for k in INPUT_FIELDS}
        self._active_signals: list[str] = []

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set_field(self, key: str, value: str) -> None:
        """Set a single structured input field."""
        if key in INPUT_FIELDS:
            self._fields[key] = value

    def set_signals(self, signals: list[str]) -> None:
        """Replace the active signal set. Signals always overwrite."""
        self._active_signals = list(signals)

    def apply_extracted(self, extracted: dict) -> None:
        """Apply a dict of extracted values from any source (text/button/attachment).

        The special key "signals" (list[str]) feeds set_signals().
        All other keys are matched against INPUT_FIELDS and ignored if unknown.
        """
        for key, value in extracted.items():
            if key == "signals":
                if isinstance(value, list):
                    self.set_signals(value)
            elif key in INPUT_FIELDS:
                self._fields[key] = str(value)
            # Unknown keys are silently ignored

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return the current state of all fields plus signals."""
        status: dict = dict(self._fields)
        status["signals_confirmed"] = len(self._active_signals) > 0
        status["active_signals"] = list(self._active_signals)
        return status

    def get_gaps(self) -> dict:
        """Return which required fields are still missing and whether signals are present."""
        missing_required = [
            f for f in REQUIRED_FIELDS if self._fields.get(f) is None
        ]
        return {
            "required": missing_required,
            "has_signals": len(self._active_signals) > 0,
        }

    def is_ready(self) -> bool:
        """Return True when the session has enough to exit INTAKE.

        Minimum: deal_stage present + at least one confirmed signal.
        """
        gaps = self.get_gaps()
        return len(gaps["required"]) == 0 and gaps["has_signals"]

    # ------------------------------------------------------------------
    # Serialisation (for persisting inside SessionState)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "fields": dict(self._fields),
            "active_signals": list(self._active_signals),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IntakeTracker":
        tracker = cls()
        for key, value in data.get("fields", {}).items():
            if key in INPUT_FIELDS and value is not None:
                tracker._fields[key] = value
        tracker._active_signals = list(data.get("active_signals", []))
        return tracker
