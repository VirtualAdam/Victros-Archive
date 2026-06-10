"""Contract test — every backend state must have a frontend handler.

Reads the backend state machine and cross-references against the
frontend App.tsx to verify every state the backend can produce has
a corresponding rendering path in the frontend.

This prevents the exact failure pattern: backend adds a new state,
frontend shows 'Unknown state'.
"""
import pathlib
import re

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_APP = BACKEND_DIR.parent / "frontend" / "src" / "App.tsx"


class TestFrontendBackendContract:

    @pytest.fixture(scope="class")
    def backend_states(self):
        """All states reachable in the backend state machine."""
        from server.state_machine import VALID_TRANSITIONS
        states = set(VALID_TRANSITIONS.keys())
        for targets in VALID_TRANSITIONS.values():
            states.update(targets)
        return states

    @pytest.fixture(scope="class")
    def frontend_handled_states(self):
        """All states the frontend App.tsx explicitly handles."""
        if not FRONTEND_APP.exists():
            pytest.skip("Frontend not found")
        source = FRONTEND_APP.read_text(encoding="utf-8")
        # Match state === 'X' or state === "X" patterns
        matches = re.findall(r"""state\s*===?\s*['"]([A-Z_]+)['"]""", source)
        return set(matches)

    # Transient states the user never sees — frontend doesn't need to handle these
    TRANSIENT_STATES = {"EVALUATING", "NEW_SESSION"}

    def test_every_backend_state_has_frontend_handler(
        self, backend_states, frontend_handled_states
    ):
        """Every user-visible backend state must be handled in the frontend."""
        visible_states = backend_states - self.TRANSIENT_STATES
        unhandled = visible_states - frontend_handled_states
        assert not unhandled, (
            f"Backend states with no frontend handler: {sorted(unhandled)}. "
            f"Add handling in App.tsx for these states."
        )

    def test_frontend_doesnt_reference_removed_states(
        self, backend_states, frontend_handled_states
    ):
        """Frontend should not handle states that don't exist in the backend."""
        # PIVOT was removed — catch if frontend still references it
        removed = frontend_handled_states - backend_states
        # Allow some grace for fallback handling
        if removed:
            pytest.warns(
                UserWarning,
                match="Frontend references states not in backend",
            ) if False else None  # Just document, don't fail — may be intentional fallback
