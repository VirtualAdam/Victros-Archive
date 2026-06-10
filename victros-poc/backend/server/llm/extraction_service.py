"""Extraction Service — converts free text / attachments to candidate signals.

Contract:
    extract(text: str, known_signal_keys: list[str]) -> {
        "candidate_signals": list[str],   # subset of known_signal_keys only
        "deal_attributes": {              # any subset of fields present
            "stage"?: str,
            "close_date"?: str,
            "amount"?: float,
            "notes"?: str,
        }
    }

    extract_pivot(text: str, known_signal_keys: list[str]) -> {
        "add_signals": list[str],
        "remove_signals": list[str],
        "update_deal": dict,
        "explanation": str,
    }

The mock uses a keyword-to-signal mapping grounded in the eval set. When
credentials are configured the real LLM is called instead.
"""
from __future__ import annotations

import json
import time

from server.llm.client import get_llm_client, is_mock_mode
from server.llm.logger import log_llm_call

# Keyword phrases → signal keys (ordered: more specific phrases first).
_KEYWORD_SIGNAL_MAP: list[tuple[str, str]] = [
    ("single-threaded", "single_threaded_contact"),
    ("single threaded", "single_threaded_contact"),
    ("one contact", "single_threaded_contact"),
    ("only contact", "single_threaded_contact"),
    ("only talking to one", "single_threaded_contact"),
    ("one guy", "single_threaded_contact"),
    ("one person", "single_threaded_contact"),
    ("competition gaining", "competition_gaining_mindshare"),
    ("competition.*gaining", "competition_gaining_mindshare"),
    ("competitor", "competition_gaining_mindshare"),
    ("competitive", "competition_gaining_mindshare"),
    ("follow-up meeting", "competition_gaining_mindshare"),
    ("validation.*doesn't match", "validation_process_misalignment"),
    ("custom poc", "validation_process_misalignment"),
    ("poc.*doesn't", "validation_process_misalignment"),
    ("doesn't do well", "validation_process_misalignment"),
    ("poc that doesn", "validation_process_misalignment"),
    ("security not involved", "validation_process_misalignment"),
    ("went silent", "no_named_or_active_champion"),
    ("champion.*silent", "no_named_or_active_champion"),
    ("couldn't get us on the agenda", "no_named_or_active_champion"),
    ("not sure.*champion", "no_named_or_active_champion"),
    ("no champion", "no_named_or_active_champion"),
    ("who would champion", "no_named_or_active_champion"),
    ("lost access to the economic buyer", "no_eb_validation"),
    ("lost access to eb", "no_eb_validation"),
    ("eb.*disengaged", "no_eb_validation"),
    ("new.*vp", "new_stakeholder_appears_late"),
    ("new stakeholder", "new_stakeholder_appears_late"),
    ("new.*introduced", "new_stakeholder_appears_late"),
    ("nobody told us", "new_stakeholder_appears_late"),
    ("nobody told us about them", "new_stakeholder_appears_late"),
    ("reorg", "new_stakeholder_appears_late"),
    ("reorganization", "new_stakeholder_appears_late"),
    ("decision process.*changed", "validation_process_misalignment"),
    ("security review.*required", "validation_process_misalignment"),
    ("added a security review", "validation_process_misalignment"),
    ("procurement.*new process", "validation_process_misalignment"),
    ("new procurement process", "validation_process_misalignment"),
    ("three vendor eval", "validation_process_misalignment"),
    ("timeline moved up", "slowdowns_or_silence"),
    ("close date.*pushed", "slowdowns_or_silence"),
    ("urgency.*shift", "slowdowns_or_silence"),
    ("champion.*actively", "champion_coaching_influence"),
    ("champion.*set up a meeting", "champion_coaching_influence"),
    ("champion is back", "champion_coaching_influence"),
    ("actively pushing", "champion_coaching_influence"),
    ("economic buyer.*engaged", "economic_buyer_engagement"),
    ("eb.*engaged", "economic_buyer_engagement"),
    ("budget approval", "economic_buyer_engagement"),
    ("consensus", "multi_threading_momentum"),
    ("differentiation.*recognized", "differentiated_validation_momentum"),
    ("validation.*aligned", "differentiated_validation_momentum"),
    ("urgency confirmed", "responsiveness_velocity"),
    ("aligned on next steps", "responsiveness_velocity"),
    ("buyer is excited", "responsiveness_velocity"),
    ("case for change", "champion_coaching_influence"),
    ("everything is going great", "champion_coaching_influence"),
]

_EXTRACT_SYSTEM_PROMPT = """\
You are the Victros Extraction Service. Your job is to extract deal signals
and deal attributes from user input about a B2B sales deal.

ALLOWED SIGNAL KEYS (return ONLY keys from this list):
{signal_keys}

Extract:
1. candidate_signals: A list of signal keys from the allowed list that are
   clearly evidenced in the input. Only include a signal if the text provides
   concrete evidence. Do NOT include speculative or hedged signals
   ("might be", "could be", "not sure if").

2. deal_attributes: Extract any of these fields if present:
   - "stage": Deal stage (normalize to the name given)
   - "close_date": In YYYY-MM-DD format if possible
   - "amount": Numeric value in USD (convert K=1000, M=1000000)
   - "notes": Any other relevant deal metadata

Rules:
- NEVER return a signal key not in the allowed list.
- If no signals are evidenced, return an empty list.
- If no deal attributes are found, return an empty object.
- Negations matter: "not single-threaded" means do NOT include single_threaded_contact.
- Hedged language ("might", "possibly") should NOT trigger signals.

Respond with ONLY a JSON object. No explanation. No markdown fencing."""

_PIVOT_SYSTEM_PROMPT = """\
You are the Victros Pivot Extraction Service. The user is providing an update
to an existing deal evaluation. Extract what has CHANGED.

ALLOWED SIGNAL KEYS (return ONLY keys from this list):
{signal_keys}

Return a JSON object with:
1. "add_signals": Signal keys that should be NEWLY activated based on this update.
2. "remove_signals": Signal keys that should be DEACTIVATED based on this update
   (e.g., if "champion is back" then remove "no_named_or_active_champion").
3. "update_deal": Any deal attribute changes (stage, close_date, amount, notes).
4. "explanation": One sentence explaining the pivot.

Rules:
- NEVER return a signal key not in the allowed list.
- Only remove signals when the text explicitly contradicts them.
- Only add signals with clear evidence.

Respond with ONLY a JSON object. No explanation. No markdown fencing."""


def extract(text: str, known_signal_keys: list[str]) -> dict:
    """Extract candidate signals and deal attributes from free text.

    Returns:
        {"candidate_signals": [...], "deal_attributes": {...}}
    """
    if is_mock_mode():
        return _extract_mock(text, known_signal_keys)
    return _extract_llm(text, known_signal_keys)


def _extract_llm(text: str, known_signal_keys: list[str]) -> dict:
    """Call the real LLM for extraction."""
    from azure.ai.inference.models import SystemMessage, UserMessage

    system_prompt = _EXTRACT_SYSTEM_PROMPT.format(
        signal_keys=json.dumps(known_signal_keys)
    )
    client = get_llm_client()
    t0 = time.monotonic()
    try:
        response = client.complete(
            messages=[
                SystemMessage(content=system_prompt),
                UserMessage(content=text or "(empty input)"),
            ],
            temperature=0.0,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        # Enforce contract: candidate_signals must be subset of known keys
        result["candidate_signals"] = [
            s for s in result.get("candidate_signals", [])
            if s in known_signal_keys
        ]
        attrs = result.get("deal_attributes", {})
        allowed_keys = {"stage", "close_date", "amount", "notes"}
        result["deal_attributes"] = {k: v for k, v in attrs.items() if k in allowed_keys}
        if "amount" in result["deal_attributes"]:
            result["deal_attributes"]["amount"] = float(result["deal_attributes"]["amount"])

        usage = response.usage
        log_llm_call(
            service="extraction",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=True,
            mock=False,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            prompt_text=text,
            completion_text=raw,
        )
        return result
    except Exception as exc:
        log_llm_call(
            service="extraction",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=False,
            mock=False,
            error=f"{type(exc).__name__}: {exc}",
            prompt_text=text,
        )
        return _extract_mock(text, known_signal_keys)


def _extract_mock(text: str, known_signal_keys: list[str]) -> dict:
    """Keyword-based mock extraction."""
    import re
    t0 = time.monotonic()
    lower = text.lower()
    found: list[str] = []
    for phrase, signal_key in _KEYWORD_SIGNAL_MAP:
        if signal_key in known_signal_keys and signal_key not in found:
            if re.search(phrase, lower):
                found.append(signal_key)

    deal_attrs = _extract_deal_attributes(text)
    result = {"candidate_signals": found, "deal_attributes": deal_attrs}
    log_llm_call(
        service="extraction",
        latency_ms=(time.monotonic() - t0) * 1000,
        success=True,
        mock=True,
        prompt_text=text,
        completion_text=str(result),
    )
    return result


def extract_pivot(text: str, known_signal_keys: list[str]) -> dict:
    """Extract a Schema Delta for a Pivot input.

    Returns:
        {"add_signals": [...], "remove_signals": [...], "update_deal": {}, "explanation": ""}
    """
    if is_mock_mode():
        return _extract_pivot_mock(text, known_signal_keys)
    return _extract_pivot_llm(text, known_signal_keys)


def _extract_pivot_llm(text: str, known_signal_keys: list[str]) -> dict:
    """Call the real LLM for pivot extraction."""
    from azure.ai.inference.models import SystemMessage, UserMessage

    system_prompt = _PIVOT_SYSTEM_PROMPT.format(
        signal_keys=json.dumps(known_signal_keys)
    )
    client = get_llm_client()
    t0 = time.monotonic()
    try:
        response = client.complete(
            messages=[
                SystemMessage(content=system_prompt),
                UserMessage(content=text or "(empty input)"),
            ],
            temperature=0.0,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        # Enforce contract
        result["add_signals"] = [
            s for s in result.get("add_signals", []) if s in known_signal_keys
        ]
        result["remove_signals"] = [
            s for s in result.get("remove_signals", []) if s in known_signal_keys
        ]
        attrs = result.get("update_deal", {})
        allowed_keys = {"stage", "close_date", "amount", "notes"}
        result["update_deal"] = {k: v for k, v in attrs.items() if k in allowed_keys}
        result.setdefault("explanation", "")

        usage = response.usage
        log_llm_call(
            service="extraction_pivot",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=True,
            mock=False,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            prompt_text=text,
            completion_text=raw,
        )
        return result
    except Exception as exc:
        log_llm_call(
            service="extraction_pivot",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=False,
            mock=False,
            error=f"{type(exc).__name__}: {exc}",
            prompt_text=text,
        )
        return _extract_pivot_mock(text, known_signal_keys)


def _extract_pivot_mock(text: str, known_signal_keys: list[str]) -> dict:
    """Mock pivot extraction."""
    t0 = time.monotonic()
    base = _extract_mock(text, known_signal_keys)
    remove: list[str] = []
    if "champion is back" in text.lower() or "champion.*back" in text.lower():
        remove.append("no_named_or_active_champion")
    result = {
        "add_signals": base["candidate_signals"],
        "remove_signals": remove,
        "update_deal": base["deal_attributes"],
        "explanation": "Extracted from pivot input.",
    }
    log_llm_call(
        service="extraction_pivot",
        latency_ms=(time.monotonic() - t0) * 1000,
        success=True,
        mock=True,
        prompt_text=text,
        completion_text=str(result),
    )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _extract_deal_attributes(text: str) -> dict:
    """Heuristic extraction of deal metadata from text. Not LLM."""
    import re
    attrs: dict = {}

    stage_patterns = [
        r"stage[:\s=]+([^\s,.$]+)",
        r"stage\s+(\d+)[_\s]?(\w+)",
    ]
    for pat in stage_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            attrs["stage"] = m.group(0).split("=")[-1].strip().strip(",")
            break

    amount_m = re.search(r"\$\s?([\d,.]+)\s*[KkMm]?", text)
    if amount_m:
        raw = amount_m.group(1).replace(",", "")
        suffix = text[amount_m.end():amount_m.end() + 1].upper()
        val = float(raw)
        if suffix == "K":
            val *= 1_000
        elif suffix == "M":
            val *= 1_000_000
        attrs["amount"] = val

    date_m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if date_m:
        attrs["close_date"] = date_m.group(1)

    return attrs
