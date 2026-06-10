"""General AI Assist — handles non-strategic requests via LLM.

Contract:
    assist(content: str) -> str

The mock returns a canned coaching-voice response. When credentials are
configured the real LLM generates a task-specific response.
"""
from __future__ import annotations

import time

from server.llm.client import get_llm_client, is_mock_mode
from server.llm.logger import log_llm_call

_MOCK_RESPONSE = (
    "Victros noted your request. Based on typical patterns in this situation, "
    "here are a few considerations to align on before proceeding. "
    "Ask the stakeholders to confirm priorities. Map the key decision criteria. "
    "Validate that the timeline reflects the actual buying process. "
    "This guidance is general — for deal-specific strategy, return to the main session."
)

_SYSTEM_PROMPT = """\
You are Victros, a strategic sales coaching assistant. The user has made a
general (non-strategic) request — an artifact, coaching question, methodology
question, roleplay, or educational inquiry.

ABSOLUTE RULES:
- Respond helpfully to the user's specific request.
- Use a professional coaching voice. Refer to yourself as "Victros" in third
  person when appropriate.
- Use observable action verbs: ask, map, align, validate, confirm, request,
  identify, demonstrate, reframe.
- NEVER activate signals, select strategy paths, or reference schema state.
  Do NOT use phrases like "activate signal", "select strategy",
  "strategy_path", "signal_key", or "candidate_signals".
- NEVER use first-person opinion language: "I think", "I believe", "I feel".
- If the request is outside your coaching scope (e.g., writing code, financial
  calculations), acknowledge politely and redirect to deal coaching.
- Keep responses concise and actionable."""


def assist(content: str) -> str:
    """Handle a general (non-strategic) user request.

    Returns:
        str — coaching-voice response. Does not modify schema state.
    """
    if is_mock_mode():
        return _assist_mock(content)
    return _assist_llm(content)


def _assist_llm(content: str) -> str:
    """Call the real LLM for general assistance."""
    from azure.ai.inference.models import SystemMessage, UserMessage

    client = get_llm_client()
    t0 = time.monotonic()
    try:
        response = client.complete(
            messages=[
                SystemMessage(content=_SYSTEM_PROMPT),
                UserMessage(content=content or "(empty input)"),
            ],
            temperature=0.4,
            max_tokens=600,
        )
        result = response.choices[0].message.content.strip()
        usage = response.usage
        log_llm_call(
            service="general_assist",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=True,
            mock=False,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            prompt_text=content,
            completion_text=result[:200],
        )
        return result
    except Exception as exc:
        log_llm_call(
            service="general_assist",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=False,
            mock=False,
            error=f"{type(exc).__name__}: {exc}",
            prompt_text=content,
        )
        return _MOCK_RESPONSE


def _assist_mock(content: str) -> str:
    """Canned mock response."""
    t0 = time.monotonic()
    result = _MOCK_RESPONSE
    log_llm_call(
        service="general_assist",
        latency_ms=(time.monotonic() - t0) * 1000,
        success=True,
        mock=True,
        prompt_text=content,
        completion_text=result[:200],
    )
    return result
