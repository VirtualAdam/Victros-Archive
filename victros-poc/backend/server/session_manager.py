"""Session Manager — file-based implementation of SessionRepository.

Used for local development without Docker. The interface is identical to
CosmosSessionRepository so the app can switch backends via STORAGE_BACKEND.
"""
from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Any

from server.db.base import SessionRepository
from server.models import (
    ActivePatterns,
    DealSnapshot,
    IntakeReadiness,
    SessionState,
)

# Canonical lever ordering — initial state
DEFAULT_LEVER_STATES = {
    "case_for_change_strength": "WEAK",
    "champion_strength": "WEAK",
    "economic_buyer_commitment": "WEAK",
    "buyer_consensus": "WEAK",
    "decision_process_alignment": "WEAK",
    "differentiation_leverage": "WEAK",
    "buyer_urgency": "WEAK",
}


class SessionManager(SessionRepository):
    """File-based session storage — identical interface to CosmosSessionRepository."""

    def __init__(self, sessions_dir: pathlib.Path) -> None:
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

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
        self._write(session)
        return session

    # ------------------------------------------------------------------
    def get_session(self, session_id: str) -> SessionState | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionState(**data)

    # ------------------------------------------------------------------
    def update_session(self, session_id: str, **fields: Any) -> SessionState:
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        for key, value in fields.items():
            setattr(session, key, value)

        session.updated_at = datetime.now(timezone.utc).isoformat()
        self._write(session)
        return session

    # ------------------------------------------------------------------
    def append_history(self, session_id: str, entry: dict) -> None:
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session.interaction_history.append(entry)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        self._write(session)

    # ------------------------------------------------------------------
    def update_state(self, session_id: str, state: str) -> SessionState:
        """Convenience wrapper: update only the state field."""
        return self.update_session(session_id, state=state)

    # ------------------------------------------------------------------
    def list_sessions(self, user_id: str) -> list[SessionState]:
        """Return sessions for the given user, sorted by updated_at descending."""
        sessions = [s for s in self.list_all_sessions() if s.user_id == user_id]
        sessions.sort(key=lambda s: s.updated_at or "", reverse=True)
        return sessions

    # ------------------------------------------------------------------
    def list_all_sessions(self) -> list[SessionState]:
        sessions = []
        for path in self.sessions_dir.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(SessionState(**data))
        return sessions

    # -- Internal ---------------------------------------------------------
    def _path(self, session_id: str) -> pathlib.Path:
        return self.sessions_dir / f"{session_id}.json"

    def _write(self, session: SessionState) -> None:
        path = self._path(session.session_id)
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
