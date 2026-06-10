"""Auth enforcement smoke tests — verify SWA rejects unauthenticated requests.

These tests hit the LIVE SWA frontend URL (not the backend directly) to confirm
that the platform auth layer is working. They catch the exact class of bug where
auth is misconfigured and anyone can access the app.

AUTH-01  Unauthenticated request to frontend → 302 redirect to /.auth/login/aad
AUTH-02  Unauthenticated request to /api/* through SWA → 401 or 302
AUTH-03  /.auth/login/aad endpoint exists and redirects to Entra
AUTH-04  /.auth/me without session returns empty/null clientPrincipal
"""
import os

import pytest
import httpx

# SWA frontend URL (not the backend Container Apps URL)
SWA_URL = os.environ.get(
    "VICTROS_SWA_URL",
    "https://<YOUR_SWA_HOSTNAME>.azurestaticapps.net",
)


@pytest.mark.auth
class TestAuthEnforcement:
    """Verify that SWA built-in auth blocks unauthenticated access."""

    def test_auth01_frontend_redirects_unauthenticated(self):
        """Unauthenticated request to / is redirected to login."""
        r = httpx.get(f"{SWA_URL}/", follow_redirects=False, timeout=10)
        # SWA should return 302 to /.auth/login/aad
        assert r.status_code == 302, f"Expected 302, got {r.status_code}"
        location = r.headers.get("location", "")
        assert "/.auth/login/aad" in location, (
            f"Expected redirect to /.auth/login/aad, got: {location}"
        )

    def test_auth02_api_rejects_unauthenticated(self):
        """Unauthenticated API request through SWA is rejected."""
        r = httpx.post(
            f"{SWA_URL}/api/session/create",
            json={"user_id": "attacker", "opportunity_id": "evil"},
            follow_redirects=False,
            timeout=10,
        )
        # Should be 401 or 302 redirect to login — NOT 201
        assert r.status_code in (401, 302), (
            f"Expected 401 or 302, got {r.status_code} — auth is NOT enforced!"
        )

    def test_auth03_login_endpoint_exists(self):
        """/.auth/login/aad redirects toward the Entra login flow."""
        r = httpx.get(
            f"{SWA_URL}/.auth/login/aad",
            follow_redirects=False,
            timeout=10,
        )
        # SWA should redirect (302) — either directly to Entra or to its
        # own intermediate auth handler (which then redirects to Entra)
        assert r.status_code in (302, 303), f"Expected 302/303, got {r.status_code}"
        location = r.headers.get("location", "")
        assert "/.auth/" in location or "victros.ciamlogin.com" in location or "login.microsoftonline.com" in location, (
            f"Expected redirect to auth flow, got: {location}"
        )

    def test_auth04_auth_me_without_session_returns_no_principal(self):
        """/.auth/me without a valid session returns null clientPrincipal."""
        r = httpx.get(f"{SWA_URL}/.auth/me", timeout=10)
        # SWA returns 200 with null clientPrincipal when not authenticated
        if r.status_code == 200:
            data = r.json()
            principal = data.get("clientPrincipal")
            assert principal is None, (
                f"Expected null clientPrincipal, got: {principal}"
            )
        else:
            # 302 redirect to login is also acceptable
            assert r.status_code in (302, 401)
