"""Abstract base class for session storage backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from server.models import SessionState


class SessionRepository(ABC):
    """Interface all session storage backends must implement."""

    @abstractmethod
    def create_session(self, user_id: str, opportunity_id: str) -> SessionState: ...

    @abstractmethod
    def get_session(self, session_id: str) -> SessionState | None: ...

    @abstractmethod
    def update_session(self, session_id: str, **fields: Any) -> SessionState: ...

    @abstractmethod
    def append_history(self, session_id: str, entry: dict) -> None: ...

    @abstractmethod
    def list_sessions(self, user_id: str) -> list[SessionState]: ...

    @abstractmethod
    def list_all_sessions(self) -> list[SessionState]: ...
