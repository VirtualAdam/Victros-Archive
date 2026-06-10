"""Progress Evaluator — Layer 7 monitoring logic.

Given a free-text progress update from the rep and the active StrategyPath,
this module determines whether the deal is on track, at risk, or has met
its exit or transition conditions.

Matching strategy: keyword/phrase overlap between the update text and the
signal lists on the strategy path. This is intentionally simple — the LLM
layer (not yet wired) will provide richer interpretation later. The schema
fields are the source of truth for what constitutes progress.

Return structure:
    {
        "status": "on_track" | "at_risk" | "neutral",
        "matched_positive": list[str],   # positive signals found in the text
        "matched_negative": list[str],   # negative signals found in the text
        "exit_detected": bool,           # exit_lever_state / exit_outcome matched
        "transition_triggered": bool,    # a transition_signal was matched
    }
"""
from __future__ import annotations

from server.models import StrategyPath


def evaluate_progress(strategy_path: StrategyPath, update_text: str) -> dict:
    """Evaluate a progress update against the active strategy path's signal lists.

    Matching is case-insensitive substring/word overlap.
    """
    text_lower = update_text.lower()

    matched_positive = _match_signals(strategy_path.positive_progress_signals, text_lower)
    matched_negative = _match_signals(strategy_path.negative_progress_signals, text_lower)

    exit_detected = _match_any(
        [strategy_path.exit_lever_state, strategy_path.exit_outcome],
        text_lower,
    )

    transition_triggered = _match_any(strategy_path.transition_signals, text_lower)

    # Determine status
    if matched_positive and not matched_negative:
        status = "on_track"
    elif matched_negative:
        status = "at_risk"
    else:
        status = "neutral"

    return {
        "status": status,
        "matched_positive": matched_positive,
        "matched_negative": matched_negative,
        "exit_detected": exit_detected,
        "transition_triggered": transition_triggered,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _match_signals(signal_phrases: list[str], text_lower: str) -> list[str]:
    """Return the subset of signal phrases that overlap with the text."""
    matched = []
    for phrase in signal_phrases:
        if _phrase_matches(phrase, text_lower):
            matched.append(phrase)
    return matched


def _match_any(phrases: list[str], text_lower: str) -> bool:
    """Return True if any phrase from the list matches the text."""
    return any(_phrase_matches(p, text_lower) for p in phrases if p)


def _phrase_matches(phrase: str, text_lower: str) -> bool:
    """Check whether a meaningful portion of the phrase appears in the text.

    Strategy: extract content words (>3 chars) from the phrase and check
    that at least half of them appear in the text. This is resilient to
    minor wording differences while still requiring a real overlap.
    """
    if not phrase:
        return False
    # Direct substring match first (handles exact quotes in tests)
    if phrase.lower() in text_lower:
        return True
    # Word-overlap fallback
    content_words = [
        w.lower() for w in phrase.replace(",", " ").split() if len(w) > 3
    ]
    if not content_words:
        return False
    hits = sum(1 for w in content_words if w in text_lower)
    # Require 60% overlap to avoid false positives from shared vocabulary
    # (e.g. "buyer" and "problem" appearing in both positive and negative phrases)
    threshold = max(2, round(len(content_words) * 0.6))
    return hits >= threshold
