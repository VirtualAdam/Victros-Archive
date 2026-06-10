"""LLM client factory and session correlation context.

The client is the single point of contact with Azure AI Inference.
All four LLM services import from here — none of them know which model
or endpoint they're talking to.

Environment variables
---------------------
VICTROS_AI_ENDPOINT   Azure AI Inference endpoint URL
VICTROS_AI_KEY        Azure AI Inference key
VICTROS_AI_DEPLOYMENT Model deployment name (default: gpt-4o)
VICTROS_FORCE_MOCK    Set to "true" to force mock mode even when
                      credentials are present (useful for UAT)

When VICTROS_AI_ENDPOINT / VICTROS_AI_KEY are absent the factory returns
None.  Services treat None as "mock mode" and execute their keyword/template
fallbacks instead of making a real API call.

Session context
---------------
The API endpoints call set_session_context(session_id) before dispatching to
any LLM service.  The logger reads it via get_session_context() so every log
line carries the right session_id without threading it through every function
signature.
"""
from __future__ import annotations

import os
from contextvars import ContextVar
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure.ai.inference import ChatCompletionsClient

# ---------------------------------------------------------------------------
# Session correlation — set once per request, read by logger
# ---------------------------------------------------------------------------
_session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)


def set_session_context(session_id: str | None) -> None:
    """Call at the start of each API request handler."""
    _session_id_var.set(session_id)


def get_session_context() -> str | None:
    """Read current session_id from context (may be None for schema endpoints)."""
    return _session_id_var.get()


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _build_client() -> "ChatCompletionsClient | None":
    """Build a ChatCompletionsClient from env vars.  Cached for the process lifetime."""
    endpoint = os.environ.get("VICTROS_AI_ENDPOINT", "").strip()
    key = os.environ.get("VICTROS_AI_KEY", "").strip()
    if not endpoint or not key:
        return None
    from azure.ai.inference import ChatCompletionsClient
    from azure.core.credentials import AzureKeyCredential
    # Azure AI Inference SDK expects the deployment in the endpoint URL
    deployment = get_deployment()
    if "/openai/deployments/" not in endpoint:
        endpoint = endpoint.rstrip("/") + f"/openai/deployments/{deployment}"
    return ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(key))


def get_llm_client() -> "ChatCompletionsClient | None":
    """Return the shared LLM client, or None when credentials are not configured."""
    return _build_client()


def get_deployment() -> str:
    """Return the model deployment name configured in the environment."""
    return os.environ.get("VICTROS_AI_DEPLOYMENT", "gpt-4o")


def is_mock_mode() -> bool:
    """True when mock logic should be used instead of real LLM calls.

    Mock mode is active when:
    - No LLM credentials are configured (VICTROS_AI_ENDPOINT / VICTROS_AI_KEY), OR
    - VICTROS_FORCE_MOCK is set to "true" (overrides even when credentials exist)
    """
    if os.environ.get("VICTROS_FORCE_MOCK", "").lower() in ("true", "1", "yes"):
        return True
    return get_llm_client() is None


def reset_client_cache() -> None:
    """Clear the cached client — useful in tests that manipulate env vars."""
    _build_client.cache_clear()
