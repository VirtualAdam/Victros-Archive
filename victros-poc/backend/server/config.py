"""Config — loads application settings from environment variables."""
from __future__ import annotations

import os
import pathlib


class ConfigError(Exception):
    """Raised when required configuration is missing."""


class AppConfig:
    """Application configuration loaded from environment."""

    def __init__(
        self,
        ai_endpoint: str,
        ai_key: str,
        schema_dir: str,
    ) -> None:
        self.ai_endpoint = ai_endpoint
        self.ai_key = ai_key
        self.schema_dir = schema_dir


def get_config() -> AppConfig:
    """Load and validate configuration from environment variables."""
    ai_endpoint = os.environ.get("VICTROS_AI_ENDPOINT")
    ai_key = os.environ.get("VICTROS_AI_KEY")

    if not ai_endpoint or not ai_key:
        raise ConfigError(
            "Missing required environment variables: "
            "VICTROS_AI_ENDPOINT and VICTROS_AI_KEY must be set."
        )

    schema_dir = os.environ.get(
        "VICTROS_SCHEMA_DIR",
        str(pathlib.Path(__file__).resolve().parent.parent / "schema"),
    )

    return AppConfig(
        ai_endpoint=ai_endpoint,
        ai_key=ai_key,
        schema_dir=schema_dir,
    )
