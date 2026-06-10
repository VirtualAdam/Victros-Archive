"""Tier 1 — Config Tests (CFG-01 → CFG-03).

Written BEFORE config.py exists.
"""
import os
import pytest


class TestConfig:
    # CFG-01: Config loads from environment variables
    def test_cfg01_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("VICTROS_AI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("VICTROS_AI_KEY", "test-key-123")
        monkeypatch.setenv("VICTROS_SCHEMA_DIR", "/tmp/schema")

        from server.config import get_config

        config = get_config()
        assert config.ai_endpoint == "https://test.openai.azure.com"
        assert config.ai_key == "test-key-123"
        assert config.schema_dir == "/tmp/schema"

    # CFG-02: Missing required env var raises clear error
    def test_cfg02_missing_required(self, monkeypatch):
        monkeypatch.delenv("VICTROS_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("VICTROS_AI_KEY", raising=False)

        from server.config import get_config, ConfigError

        with pytest.raises(ConfigError):
            get_config()

    # CFG-03: Schema dir path resolves correctly
    def test_cfg03_schema_path(self, monkeypatch):
        import pathlib

        monkeypatch.setenv("VICTROS_AI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("VICTROS_AI_KEY", "test-key-123")
        # Don't set VICTROS_SCHEMA_DIR — should default to backend/schema

        from server.config import get_config

        config = get_config()
        assert config.schema_dir is not None
