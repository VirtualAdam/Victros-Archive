"""Post-deploy smoke test — verifies live endpoint works."""
import os
import pytest
import httpx

LIVE_URL = os.environ.get(
    "VICTROS_LIVE_URL",
    "https://<YOUR_CONTAINER_APP_FQDN>",
)


@pytest.mark.smoke
class TestDeploySmoke:
    def test_health(self):
        """Live health endpoint returns ok."""
        r = httpx.get(f"{LIVE_URL}/health", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_create_session_returns_intent_capture(self):
        """Creating a session on live returns INTENT_CAPTURE state."""
        r = httpx.post(
            f"{LIVE_URL}/api/session/create",
            json={"user_id": "smoke_test", "opportunity_id": "smoke_deal"},
            timeout=10,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["state"] == "INTENT_CAPTURE"
        assert "prompt" in data

    def test_minimal_flow(self):
        """Smoke: create → intent → situation validation works."""
        r = httpx.post(
            f"{LIVE_URL}/api/session/create",
            json={"user_id": "smoke_test", "opportunity_id": "smoke_flow"},
            timeout=10,
        )
        sid = r.json()["session_id"]

        r = httpx.post(
            f"{LIVE_URL}/api/session/{sid}/input",
            json={"input_type": "text", "content": "Testing deal flow"},
            timeout=10,
        )
        assert r.json()["state"] == "SITUATION_VALIDATION"
