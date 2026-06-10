"""Tests for server/llm/client.py and server/llm/logger.py (LC-01 → LC-10)."""
from __future__ import annotations

import json
import logging
import os

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _reset(monkeypatch):
    """Clear cached client and strip AI env vars."""
    from server.llm import client as c
    c.reset_client_cache()
    monkeypatch.delenv("VICTROS_AI_ENDPOINT", raising=False)
    monkeypatch.delenv("VICTROS_AI_KEY", raising=False)
    monkeypatch.delenv("VICTROS_AI_DEPLOYMENT", raising=False)
    monkeypatch.delenv("VICTROS_FORCE_MOCK", raising=False)


# ---------------------------------------------------------------------------
class TestLLMClient:

    # LC-01: is_mock_mode() returns True when credentials are absent
    def test_lc01_mock_mode_when_no_creds(self, monkeypatch):
        _reset(monkeypatch)
        from server.llm.client import is_mock_mode
        assert is_mock_mode() is True

    # LC-02: get_llm_client() returns None when credentials are absent
    def test_lc02_get_client_returns_none_without_creds(self, monkeypatch):
        _reset(monkeypatch)
        from server.llm.client import get_llm_client
        assert get_llm_client() is None

    # LC-03: get_deployment() returns "gpt-4o" by default
    def test_lc03_default_deployment(self, monkeypatch):
        _reset(monkeypatch)
        from server.llm.client import get_deployment
        assert get_deployment() == "gpt-4o"

    # LC-04: get_deployment() honours VICTROS_AI_DEPLOYMENT env var
    def test_lc04_custom_deployment(self, monkeypatch):
        _reset(monkeypatch)
        monkeypatch.setenv("VICTROS_AI_DEPLOYMENT", "Phi-4")
        from server.llm.client import get_deployment
        assert get_deployment() == "Phi-4"

    # LC-05: set_session_context / get_session_context round-trip
    def test_lc05_session_context_roundtrip(self):
        from server.llm.client import get_session_context, set_session_context
        set_session_context("sess-abc-123")
        assert get_session_context() == "sess-abc-123"
        set_session_context(None)
        assert get_session_context() is None

    # LC-06: reset_client_cache() clears the lru_cache (no exception)
    def test_lc06_reset_cache(self, monkeypatch):
        _reset(monkeypatch)
        from server.llm.client import get_llm_client, reset_client_cache
        get_llm_client()   # prime
        reset_client_cache()
        assert get_llm_client() is None  # still None — creds still absent

    # LC-11: VICTROS_FORCE_MOCK=true forces mock mode even with credentials
    def test_lc11_force_mock_overrides_credentials(self, monkeypatch):
        _reset(monkeypatch)
        monkeypatch.setenv("VICTROS_AI_ENDPOINT", "https://fake.openai.azure.com/")
        monkeypatch.setenv("VICTROS_AI_KEY", "fake-key-for-test")
        monkeypatch.setenv("VICTROS_FORCE_MOCK", "true")
        from server.llm.client import is_mock_mode
        assert is_mock_mode() is True

    # LC-12: Without force mock, credentials present means not mock
    def test_lc12_no_force_mock_with_creds_means_live(self, monkeypatch):
        _reset(monkeypatch)
        monkeypatch.setenv("VICTROS_AI_ENDPOINT", "https://fake.openai.azure.com/")
        monkeypatch.setenv("VICTROS_AI_KEY", "fake-key-for-test")
        from server.llm.client import is_mock_mode
        assert is_mock_mode() is False


# ---------------------------------------------------------------------------
class TestLLMLogger:

    def _capture_log(self):
        """Return a list that accumulates log records from victros.llm."""
        records: list[logging.LogRecord] = []

        class _Handler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _Handler()
        logger = logging.getLogger("victros.llm")
        logger.addHandler(handler)
        return records, handler, logger

    def teardown_method(self, method):
        # Remove any handlers added during the test
        logger = logging.getLogger("victros.llm")
        logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.Handler) or h.stream is not None]  # noqa

    # LC-07: log_llm_call emits valid JSON
    def test_lc07_emits_valid_json(self):
        from server.llm.client import set_session_context
        from server.llm.logger import log_llm_call

        records, handler, logger = self._capture_log()
        set_session_context("sess-test-007")

        log_llm_call(service="test_svc", latency_ms=12.5, success=True, mock=True)

        logger.removeHandler(handler)
        assert len(records) >= 1
        payload = json.loads(records[-1].getMessage())
        assert payload["event"] == "llm_call"
        assert payload["service"] == "test_svc"
        assert payload["session_id"] == "sess-test-007"
        assert payload["mock"] is True
        assert payload["success"] is True
        assert payload["latency_ms"] == 12.5

    # LC-08: error field only present when error is provided
    def test_lc08_error_field(self):
        from server.llm.logger import log_llm_call

        records, handler, logger = self._capture_log()

        log_llm_call(service="test_svc", latency_ms=1.0, success=False, mock=True, error="TimeoutError")

        logger.removeHandler(handler)
        payload = json.loads(records[-1].getMessage())
        assert payload["error"] == "TimeoutError"
        assert payload["success"] is False

    # LC-09: dev mode fields absent by default
    def test_lc09_no_dev_fields_by_default(self, monkeypatch):
        monkeypatch.setenv("LLM_DEV_LOGGING", "false")
        # Re-import to pick up the env var (logger reads it at module load)
        import importlib
        import server.llm.logger as log_mod
        importlib.reload(log_mod)

        records, handler, logger = self._capture_log()
        log_mod.log_llm_call(
            service="test_svc",
            latency_ms=1.0,
            success=True,
            mock=True,
            prompt_text="secret prompt",
            completion_text="secret result",
        )
        logger.removeHandler(handler)
        payload = json.loads(records[-1].getMessage())
        assert "prompt_text" not in payload
        assert "completion_text" not in payload

    # LC-10: dev mode fields present when LLM_DEV_LOGGING=true
    def test_lc10_dev_fields_when_enabled(self, monkeypatch):
        monkeypatch.setenv("LLM_DEV_LOGGING", "true")
        import importlib
        import server.llm.logger as log_mod
        importlib.reload(log_mod)

        records, handler, logger = self._capture_log()
        log_mod.log_llm_call(
            service="test_svc",
            latency_ms=1.0,
            success=True,
            mock=True,
            prompt_text="the prompt",
            completion_text="the result",
        )
        logger.removeHandler(handler)
        payload = json.loads(records[-1].getMessage())
        assert payload["prompt_text"] == "the prompt"
        assert payload["completion_text"] == "the result"
