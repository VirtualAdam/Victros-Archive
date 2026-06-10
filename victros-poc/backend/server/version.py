"""Victros backend version tracking.

The version is bumped manually for each release. The git SHA and build
timestamp are populated at build time via environment variables, or
read from git at runtime during local development.
"""
from __future__ import annotations

import os
import subprocess

# Semantic version — bump this on each release.
VERSION = "1.3.0"

# Label for the current iteration.
ITERATION = "SRS-v1.3"


def get_git_sha() -> str:
    """Return the short git SHA, preferring the BUILD_SHA env var."""
    sha = os.environ.get("BUILD_SHA", "").strip()
    if sha:
        return sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_version_info() -> dict:
    """Return the full version payload."""
    return {
        "version": VERSION,
        "iteration": ITERATION,
        "sha": get_git_sha(),
    }
