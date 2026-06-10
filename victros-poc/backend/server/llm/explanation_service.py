"""Explanation Service — generates coaching narrative from a DecisionResult.

Contract:
    explain(decision_result: dict, context: str) -> str

    context is one of: "diagnosis" | "tradeoff" | "monitoring" | "summary"

The mock builds a deterministic template response. When credentials are
configured the real LLM generates the coaching narrative.
"""
from __future__ import annotations

import json
import time

from server.llm.client import get_llm_client, is_mock_mode
from server.llm.logger import log_llm_call

# Persona phrases used in responses — no first-person opinion language.
_PROHIBITED_PHRASES = ["I think", "I believe", "I feel", "In my opinion"]

# Observable verbs per spec.
_OBSERVABLE_VERBS = ["ask", "map", "align", "validate", "confirm", "request", "identify", "demonstrate", "reframe", "document", "assess", "recommend", "archive"]

_SYSTEM_PROMPT = """\
You are Victros, a strategic sales coaching system. You generate coaching
narratives from structured deal analysis results. You speak in a professional,
third-person coaching voice.

ABSOLUTE RULES:
- NEVER use first-person opinion language: "I think", "I believe", "I feel",
  "In my opinion" are strictly prohibited.
- Always refer to yourself as "Victros" (third person).
- Use observable action verbs: ask, map, align, validate, confirm, request,
  identify, demonstrate, reframe, document, assess, recommend.
- Begin with "Victros identified..." when describing findings.
- Present structural implications BEFORE recommendations.

CONTEXT MODE: {context}

Context-specific instructions:
- diagnosis: Present the primary pattern, explain the structural risk/implication,
  then recommend the strategy path and list representative actions.
- tradeoff: Present both primary and secondary patterns. Offer three resolution
  options: Focus (primary first), Combine (address both), Sequence (primary then
  secondary). Ask the user to confirm which approach fits their capacity.
- monitoring: Check progress on the active strategy. Present the action taken
  and ask for outcome confirmation: Yes (expected result), Partially (some
  progress), No (no result). Explain how the response will inform next steps.
- summary: Summarize the session: active signals, lever states that advanced
  beyond WEAK, and session status. Do not recommend new actions.

DECISION RESULT (structured analysis output):
{decision_result}

Generate the coaching narrative for this context. Be concise and actionable."""


def explain(decision_result: dict, context: str = "diagnosis") -> str:
    """Generate a coaching-voice explanation from a DecisionResult."""
    if is_mock_mode():
        return _explain_mock(decision_result, context)
    return _explain_llm(decision_result, context)


def _explain_llm(decision_result: dict, context: str) -> str:
    """Call the real LLM for explanation generation."""
    from azure.ai.inference.models import SystemMessage, UserMessage

    system_prompt = _SYSTEM_PROMPT.format(
        context=context,
        decision_result=json.dumps(decision_result, indent=2),
    )
    client = get_llm_client()
    t0 = time.monotonic()
    try:
        response = client.complete(
            messages=[
                SystemMessage(content=system_prompt),
                UserMessage(content=f"Generate the {context} coaching narrative."),
            ],
            temperature=0.3,
            max_tokens=800,
        )
        result = response.choices[0].message.content.strip()
        usage = response.usage
        log_llm_call(
            service="explanation",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=True,
            mock=False,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            prompt_text=f"context={context} primary={decision_result.get('primary_pattern')}",
            completion_text=result[:200],
        )
        return result
    except Exception as exc:
        log_llm_call(
            service="explanation",
            latency_ms=(time.monotonic() - t0) * 1000,
            success=False,
            mock=False,
            error=f"{type(exc).__name__}: {exc}",
            prompt_text=f"context={context}",
        )
        return _explain_mock(decision_result, context)


def _explain_mock(decision_result: dict, context: str) -> str:
    """Template-based mock explanation."""
    primary = decision_result.get("primary_pattern")
    strategy = decision_result.get("strategy_path")
    actions = decision_result.get("representative_actions", [])
    secondary = decision_result.get("secondary_patterns", [])

    t0 = time.monotonic()
    if context == "summary":
        result = _render_summary(decision_result)
    elif context == "tradeoff":
        result = _render_tradeoff(primary, secondary, strategy)
    elif context == "monitoring":
        result = _render_monitoring(primary, strategy, actions)
    else:
        result = _render_diagnosis(primary, strategy, actions, secondary)

    log_llm_call(
        service="explanation",
        latency_ms=(time.monotonic() - t0) * 1000,
        success=True,
        mock=True,
        prompt_text=f"context={context} primary={primary} strategy={strategy}",
        completion_text=result[:200],
    )
    return result


# ---------------------------------------------------------------------------
# Template renderers — each satisfies its context's structural contracts.
# ---------------------------------------------------------------------------

def _render_diagnosis(
    primary: str | None,
    strategy: str | None,
    actions: list[str],
    secondary: list[str],
) -> str:
    if not primary or not strategy:
        return (
            "Victros identified no active structural patterns at this time. "
            "Confirm the current deal signals to enable a strategy recommendation."
        )

    action_lines = "\n".join(f"  - {a}" for a in actions) if actions else "  (no actions)"
    secondary_note = (
        f" Secondary patterns also present: {', '.join(secondary)}." if secondary else ""
    )

    return (
        f"Victros identified the following structural condition: {primary}.\n\n"
        f"This pattern indicates a structural risk that, if unaddressed, will erode deal momentum "
        f"and reduce the probability of a favorable outcome.{secondary_note}\n\n"
        f"Recommended strategic focus: {strategy}. "
        f"The objective is to ask the right questions, map stakeholder priorities, "
        f"align the evaluation process, and validate commitment from the key roles.\n\n"
        f"Representative actions to execute:\n{action_lines}"
    )


def _render_tradeoff(
    primary: str | None,
    secondary: list[str],
    strategy: str | None,
) -> str:
    others = ", ".join(secondary) if secondary else "none"
    return (
        f"Victros identified two active structural patterns: {primary} (primary) "
        f"and {others} (secondary).\n\n"
        f"You have three options for how to proceed:\n"
        f"  - Focus: concentrate resources on {primary} first.\n"
        f"  - Combine: address both patterns simultaneously with {strategy}.\n"
        f"  - Sequence: resolve {primary} before addressing secondary patterns.\n\n"
        f"Confirm which approach aligns with your current capacity and deal timeline."
    )


def _render_monitoring(
    primary: str | None,
    strategy: str | None,
    actions: list[str],
) -> str:
    action_context = actions[0] if actions else "the selected action"
    return (
        f"Victros is monitoring progress on {strategy} (addressing {primary}).\n\n"
        f"After executing {action_context}, confirm the outcome:\n"
        f"  - Yes: the action produced the expected result.\n"
        f"  - Partially: some progress was made but the condition persists.\n"
        f"  - No: the action did not produce the expected result.\n\n"
        f"Your response will allow Victros to validate the current strategy or recommend a pivot."
    )


def _render_summary(decision_result: dict) -> str:
    signals = decision_result.get("active_signals", [])
    levers = decision_result.get("lever_states", {})
    advanced = [k for k, v in levers.items() if v != "WEAK"]

    return (
        f"Victros identified the following active signals during this session: "
        f"{', '.join(signals) if signals else 'none'}.\n\n"
        f"Levers that advanced beyond WEAK: {', '.join(advanced) if advanced else 'none'}.\n\n"
        f"The session is complete. You may request a new evaluation or continue with updated deal information."
    )
