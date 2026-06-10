"""Intent Router — classifies user input as 'strategic' or 'general'.

Contract:
    classify(text: str) -> {"category": "strategic" | "general", "confidence": float}

The mock uses a keyword heuristic grounded in the eval set. When credentials
are configured and VICTROS_FORCE_MOCK is not set, the real LLM is called.
"""
from __future__ import annotations

import json
import time

from server.llm.client import get_llm_client, is_mock_mode
from server.llm.logger import log_llm_call

# Keywords that strongly indicate strategic (deal signal) language.
_STRATEGIC_KEYWORDS = [
    "champion", "champ", "economic buyer", "single-threaded", "single threaded",
    "competition", "competitor", "competitive", "validation", "poc",
    "stakeholder", "decision process", "deal stage", "close date",
    "budget", "procurement", "reorg", "reorganization", "re-org", "consensus",
    "blocking", "went silent", "ghosted", "disengaged", "no path", "deal blocked",
    "urgency", "close date pushed", "new vp", "new stakeholder",
    "buying group", "security review", "security team", "follow-up meeting",
    "agenda", "mindshare", "compliance director", "wants to move fast",
    "move fast", "evaluation", "deal", "stage moved", "stage just moved",
    "ciso", "cto", "cro",  # executive sponsor abbreviations
    " eb ", " eb'", " eb,",  # economic buyer abbreviation with word boundaries
]

# Patterns that override strategic keywords — these indicate coaching/artifact requests.
_GENERAL_OVERRIDE_PATTERNS = [
    "what does ", "what is ", "what are ", "what makes ",
    "what would happen", "what if ",
    "how do i ", "how to ", "how should ",
    "what's the best", "what is the best",
    "write me ", "draft ", "write an email", "write a ",
    "battle card", "roleplay", "role play",
    "general coaching", "explain ", "define ",
    "could you roleplay", "can you roleplay",
]

# Concrete deal-event phrases — these signal something actually happened in the deal.
# Their presence overrides the general override (artifact + deal event = strategic).
_SIGNAL_EVENT_PHRASES = [
    "went silent", "gone silent", "radio silent", "ghosted",
    "just went", "just got", "just changed", "just moved",
    "just introduced", "just joined", "just added",
    "got pushed", "was introduced", "is blocking", "are blocking",
    "lost access", "no path",
]

_SYSTEM_PROMPT = """\
You are the Victros Intent Router. Your sole job is to classify user input
into exactly one of two categories:

- "strategic": The input describes, references, or implies a real deal
  situation that should be analysed by the Victros strategic reasoning engine.
  This includes deal updates, signal language (champion went silent, competitor
  gaining traction, lost access to EB, etc.), stakeholder changes, timeline
  shifts, or any input where the user is reporting what is happening in an
  active deal.

- "general": The input is a request for an artifact (email draft, battle card,
  summary), a coaching or methodology question, a definition request, a
  roleplay, or anything that does NOT describe an active deal situation
  requiring strategic analysis.

Key rules:
- If the input contains BOTH a general request AND strategic deal information,
  classify as "strategic" — deal signals take priority.
- Questions ABOUT strategic concepts (e.g. "What does single-threaded mean?")
  are "general" — the user is asking for education, not reporting a deal state.
- Artifact requests that mention deal terms in passing (e.g. "Draft an email
  to my champion") are "general" — the user wants an artifact, not analysis.
- Never invent a third category. Always return exactly "strategic" or "general".

Respond with ONLY a JSON object: {"category": "...", "confidence": 0.0-1.0}
No explanation. No markdown fencing. Just the JSON object."""


def classify(text: str) -> dict:
    """Classify user input as 'strategic' or 'general'.

    Returns:
        {"category": "strategic" | "general", "confidence": float}
    """
    if is_mock_mode():
        return _classify_mock(text)
    return _classify_llm(text)


def _classify_llm(text: str) -> dict:
    """Call the real LLM for classification."""
    from azure.ai.inference.models import SystemMessage, UserMessage

    client = get_llm_client()
    t0 = time.monotonic()
    try:
        response = client.complete(
            messages=[
                SystemMessage(content=_SYSTEM_PROMPT),
                UserMessage(content=text or "(empty input)"),
            ],
            temperature=0.0,
            max_tokens=60,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        # Validate shape
        if result.get("category") not in ("strategic", "general"):
            result["category"] = "general"
        result["confidence"] = float(result.get("confidence", 0.5))
        result["confidence"] = max(0.0, min(1.0, result["confidence"]))

        usage = response.usage
        log_llm_call(
            service="intent_router",
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
            service="intent_router",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=False,
            mock=False,
            error=f"{type(exc).__name__}: {exc}",
            prompt_text=text,
        )
        # Fallback to mock on error
        return _classify_mock(text)


def _classify_mock(text: str) -> dict:
    """Keyword-based mock classification.

    General override patterns take priority — coaching questions and artifact
    requests are "general" even when they mention strategic keywords.
    """
    t0 = time.monotonic()
    lower = text.lower()
    has_signal_event = any(p in lower for p in _SIGNAL_EVENT_PHRASES)
    is_general_override = any(p in lower for p in _GENERAL_OVERRIDE_PATTERNS)
    is_strategic = any(kw in lower for kw in _STRATEGIC_KEYWORDS)
    # Artifact/coaching requests are general UNLESS an active deal event phrase is present
    category = "strategic" if (is_strategic and (not is_general_override or has_signal_event)) else "general"
    result = {"category": category, "confidence": 0.9}
    log_llm_call(
        service="intent_router",
        latency_ms=(time.monotonic() - t0) * 1000,
        success=True,
        mock=True,
        prompt_text=text,
        completion_text=str(result),
    )
    return result
