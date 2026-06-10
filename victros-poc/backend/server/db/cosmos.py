"""Cosmos DB session repository — used in cloud and local emulator."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from server.db.base import SessionRepository
from server.models import (
    ActivePatterns,
    DealSnapshot,
    IntakeReadiness,
    SessionState,
)

# Lever defaults kept in sync with FileSessionRepository
DEFAULT_LEVER_STATES = {
    "case_for_change_strength": "WEAK",
    "champion_strength": "WEAK",
    "economic_buyer_commitment": "WEAK",
    "buyer_consensus": "WEAK",
    "decision_process_alignment": "WEAK",
    "differentiation_leverage": "WEAK",
    "buyer_urgency": "WEAK",
}

# System properties Cosmos adds to every document — must be stripped before
# constructing a SessionState.
_COSMOS_SYSTEM_PROPS = {"_rid", "_self", "_etag", "_attachments", "_ts"}


def _to_session(doc: dict) -> SessionState:
    """Convert a raw Cosmos document into a SessionState, stripping metadata."""
    clean = {k: v for k, v in doc.items() if k not in _COSMOS_SYSTEM_PROPS and k != "id"}
    return SessionState(**clean)


class CosmosSessionRepository(SessionRepository):
    """Session repository backed by Azure Cosmos DB (or the local emulator)."""

    DB_NAME = "victros"
    CONTAINER_NAME = "sessions"

    def __init__(self, connection_string: str, verify_ssl: bool = True) -> None:
        self._client = CosmosClient.from_connection_string(
            connection_string,
            connection_verify=verify_ssl,
        )
        db = self._client.create_database_if_not_exists(self.DB_NAME)
        self._container = db.create_container_if_not_exists(
            id=self.CONTAINER_NAME,
            partition_key=PartitionKey(path="/session_id"),
        )

    # ------------------------------------------------------------------
    def create_session(self, user_id: str, opportunity_id: str) -> SessionState:
        now = datetime.now(timezone.utc).isoformat()
        session = SessionState(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            opportunity_id=opportunity_id,
            state="NEW_SESSION",
            deal_snapshot=None,
            active_signals=[],
            active_patterns=ActivePatterns(),
            selected_strategy_path=None,
            lever_states=dict(DEFAULT_LEVER_STATES),
            interaction_history=[],
            intake_readiness=IntakeReadiness(),
            created_at=now,
            updated_at=now,
        )
        doc = session.model_dump()
        doc["id"] = session.session_id
        self._container.create_item(doc)
        return session

    # ------------------------------------------------------------------
    def get_session(self, session_id: str) -> SessionState | None:
        try:
            doc = self._container.read_item(session_id, partition_key=session_id)
            return _to_session(doc)
        except CosmosResourceNotFoundError:
            return None

    # ------------------------------------------------------------------
    def update_session(self, session_id: str, **fields: Any) -> SessionState:
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        for key, value in fields.items():
            setattr(session, key, value)

        session.updated_at = datetime.now(timezone.utc).isoformat()
        doc = session.model_dump()
        doc["id"] = session.session_id
        self._container.replace_item(session_id, doc)
        return session

    # ------------------------------------------------------------------
    def append_history(self, session_id: str, entry: dict) -> None:
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session.interaction_history.append(entry)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        doc = session.model_dump()
        doc["id"] = session.session_id
        self._container.replace_item(session_id, doc)

    # ------------------------------------------------------------------
    def list_sessions(self, user_id: str) -> list[SessionState]:
        query = "SELECT * FROM c WHERE c.user_id = @user_id"
        params = [{"name": "@user_id", "value": user_id}]
        items = self._container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True,
        )
        return [_to_session(doc) for doc in items]

    # ------------------------------------------------------------------
    def list_all_sessions(self) -> list[SessionState]:
        items = self._container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True,
        )
        return [_to_session(doc) for doc in items]
