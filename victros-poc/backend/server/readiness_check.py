"""Readiness Check — determines if session can proceed to EVALUATING."""
from __future__ import annotations

from server.models import IntakeReadiness

# The 6 required intake fields in mandatory collection order.
REQUIRED_INTAKE_FIELDS = [
    "deal_stage",
    "offering_type",
    "offering_usage",
    "usage_depth",
    "deal_amount",
    "deal_close_date",
]


def check_readiness(readiness: IntakeReadiness) -> dict:
    """Check whether the session is ready for the Decision Engine.

    Requirements (data-flow-logic.md S4):
    - All 6 required fields must be present (not "missing")
    - signals_confirmed must be True (at least one signal confirmed)
    """
    missing = []

    for field in REQUIRED_INTAKE_FIELDS:
        value = getattr(readiness, field, "missing")
        if value == "missing":
            missing.append(field)

    if not readiness.signals_confirmed:
        missing.append("signals")

    return {
        "ready": len(missing) == 0,
        "missing": missing,
    }
