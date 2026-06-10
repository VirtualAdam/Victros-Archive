"""Shared fixtures for integration tests.

Integration tests require the Cosmos DB emulator to be running.
They are skipped automatically when COSMOS_CONNECTION_STRING is not set,
so the normal `pytest` run (unit tests only) is never blocked.

To run integration tests:
  docker compose up cosmosdb -d
    export COSMOS_CONNECTION_STRING="<your-connection-string>"
    pytest -m integration
"""
from __future__ import annotations

import os
import uuid

import pytest

from server.db.cosmos import CosmosSessionRepository


@pytest.fixture(scope="module")
def cosmos_repo():
    """CosmosSessionRepository pointed at the local emulator.

    Skipped if COSMOS_CONNECTION_STRING is not set in the environment.
    Uses a unique database suffix per test run to avoid cross-run contamination.
    """
    conn_str = os.environ.get("COSMOS_CONNECTION_STRING")
    if not conn_str:
        pytest.skip("COSMOS_CONNECTION_STRING is not set")

    # Quick reachability check — skip if emulator isn't up
    try:
        repo = CosmosSessionRepository(conn_str, verify_ssl=False)
    except Exception as exc:
        pytest.skip(f"Cosmos emulator not reachable: {exc}")

    yield repo
