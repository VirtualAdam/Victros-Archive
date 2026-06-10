"""Structured LLM call logger.

Emits one JSON line to stdout per LLM service call.  Azure Monitor /
Application Insights picks up stdout JSON automatically when deployed.

Normal mode (default)
---------------------
Logs: service, model, session_id, mock, prompt_tokens, completion_tokens,
      latency_ms, success, error.

Dev mode — set LLM_DEV_LOGGING=true
---------------------
Also logs: prompt_text, completion_text.
Use only during local development.  These fields may contain PII
(opportunity names, company details) and should never be enabled in
production.

Usage
-----
    from server.llm.logger import log_llm_call

    t0 = time.monotonic()
    result = do_work(...)
    log_llm_call(
        service="extraction",
        latency_ms=(time.monotonic() - t0) * 1000,
        success=True,
        prompt_tokens=0,        # 0 for mocks
        completion_tokens=0,    # 0 for mocks
        mock=True,
        # dev-mode only (ignored in production):
        prompt_text=input_text,
        completion_text=str(result),
    )
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from server.llm.client import get_deployment, get_session_context

# One Python logger for the whole LLM subsystem.  Integrators can attach
# any handler; the default StreamHandler writes to stdout.
_log = logging.getLogger("victros.llm")

if not _log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.DEBUG)
    _log.propagate = False

_DEV_LOGGING = os.environ.get("LLM_DEV_LOGGING", "").lower() in ("true", "1", "yes")


def log_llm_call(
    *,
    service: str,
    latency_ms: float,
    success: bool,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    mock: bool = False,
    error: str | None = None,
    # dev-mode fields — ignored unless LLM_DEV_LOGGING=true
    prompt_text: str | None = None,
    completion_text: str | None = None,
) -> None:
    """Emit one structured log line for an LLM service call."""
    record: dict[str, Any] = {
        "event": "llm_call",
        "service": service,
        "model": "mock" if mock else get_deployment(),
        "session_id": get_session_context(),
        "mock": mock,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "latency_ms": round(latency_ms, 2),
        "success": success,
    }
    if error:
        record["error"] = error
    if _DEV_LOGGING:
        if prompt_text is not None:
            record["prompt_text"] = prompt_text
        if completion_text is not None:
            record["completion_text"] = completion_text

    _log.info(json.dumps(record))
