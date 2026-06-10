"""Pattern Diagnostics — Layer 3 of the SRS system flow.

After the decision engine activates patterns (EVALUATING), the user must
validate them before a strategy path is selected. This module:

  1. Formats the activated pattern group into a presentation structure
     with meta-explanation and per-pattern summaries.

  2. Processes the user's binary confirmation response:
     - confirm_all → PRESENTING_DIAGNOSIS (system determined priority stands)
     - reject_all  → INTAKE (signals cleared, re-collect)

Per data-flow-logic.md S7:
  - At most 1 primary + 1 secondary pattern shown
  - User response is binary — no subset selection
  - Priority Pattern is engine-determined, not user-selected
"""
from __future__ import annotations

from server.models import Pattern

_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def format_pattern_group(patterns: list[Pattern]) -> dict:
    """Format an activated pattern list into a user-facing presentation structure.

    Limits display to at most primary (index 0) + one secondary (index 1).
    Patterns are sorted by severity CRITICAL first.
    """
    needs_confirmation = len(patterns) > 0

    # Sort by severity so highest-priority appears first
    patterns = sorted(patterns, key=lambda p: _SEVERITY_RANK.get(p.severity, 9))

    # Limit to at most 2 for display (UAT12-11)
    display_patterns = patterns[:2]

    items = [
        {
            "key": p.key,
            "name": p.name,
            "summary": p.summary,
            "diagnostic_questions": p.diagnostic_questions,
            "resolution_type": p.resolution_type,
            "severity": p.severity,
            "polarity": p.polarity,
            "role": "primary" if i == 0 else "secondary",
        }
        for i, p in enumerate(display_patterns)
    ]

    meta_explanation = _build_meta_explanation(display_patterns)

    return {
        "patterns": items,
        "meta_explanation": meta_explanation,
        "needs_confirmation": needs_confirmation,
        "options": {
            "confirm_all": "Yes, this matches what I'm seeing",
            "reject_all": "No, this doesn't reflect the situation",
        },
    }


def process_pattern_confirmation(
    activated_patterns: list[Pattern],
    response: str,
    confirmed_keys: list[str] | None = None,
) -> dict:
    """Process the user's binary confirmation response.

    Args:
        activated_patterns: The full list of engine-activated patterns.
        response: One of "confirm_all", "reject_all".
        confirmed_keys: Ignored — kept for backward compatibility.

    Returns:
        {
            "confirmed_patterns": list[str],
            "next_state": str,
        }
    """
    if response == "reject_all":
        return {"confirmed_patterns": [], "next_state": "INTAKE"}

    if response in ("confirm_all", "confirm_subset"):
        # confirm_subset treated as confirm_all for backward compat
        keys = [p.key for p in activated_patterns]
        return {"confirmed_patterns": keys, "next_state": "PRESENTING_DIAGNOSIS"}

    return {"confirmed_patterns": [], "next_state": "INTAKE"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_meta_explanation(patterns: list[Pattern]) -> str:
    if not patterns:
        return ""
    if len(patterns) == 1:
        p = patterns[0]
        return (
            f"The analysis identified one active pattern: {p.name}. "
            f"{p.summary}"
        )
    return (
        f"The analysis identified a primary pattern: {patterns[0].name} — "
        f"{patterns[0].summary} "
        f"A secondary pattern is also present: {patterns[1].name} — "
        f"{patterns[1].summary}"
    )
