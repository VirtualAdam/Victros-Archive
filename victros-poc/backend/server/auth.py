"""Authentication helpers for Container Apps Easy Auth + Entra External ID.

When Container Apps Easy Auth is enabled, every authenticated request carries:
  X-MS-CLIENT-PRINCIPAL: base64-encoded JSON with user claims
  X-MS-CLIENT-PRINCIPAL-ID: the user's object ID (shortcut header)
  X-MS-CLIENT-PRINCIPAL-NAME: the user's display name

This module extracts user identity from those headers. In local dev (no Easy
Auth), the headers are absent and the functions return None, allowing the
calling endpoint to fall back to request-body values.

Claim types (Entra External ID):
  oid / sub          — stable unique user ID (use this as user_id in sessions)
  preferred_username — email address
  roles              — list of app roles assigned in Entra
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)

# The claim type used for the stable user identifier
_OID_CLAIM = "oid"
_PREFERRED_USERNAME_CLAIM = "preferred_username"
_ROLES_CLAIM = "roles"

# App role required to trigger snapshot generation
SNAPSHOT_ADMIN_ROLE = "snapshot.generate"


def _decode_principal(header_value: str) -> dict[str, Any] | None:
    """Decode the X-MS-CLIENT-PRINCIPAL base64 JSON payload."""
    try:
        decoded = base64.b64decode(header_value + "==").decode("utf-8")
        return json.loads(decoded)
    except Exception:
        logger.warning("Failed to decode X-MS-CLIENT-PRINCIPAL header")
        return None


def _get_claim(principal: dict[str, Any], claim_type: str) -> str | None:
    """Extract a single claim value from the principal claims list."""
    for claim in principal.get("claims", []):
        if claim.get("typ") == claim_type:
            return claim.get("val")
    return None


def _get_all_claims(principal: dict[str, Any], claim_type: str) -> list[str]:
    """Extract all values for a repeated claim (e.g. roles)."""
    return [
        c.get("val", "")
        for c in principal.get("claims", [])
        if c.get("typ") == claim_type
    ]


def get_caller_user_id(request: Request) -> str | None:
    """Return the stable Entra object ID of the authenticated caller.

    Returns None when Easy Auth headers are absent (local dev / unauthenticated).
    Callers should fall back to request body when this returns None.
    """
    header = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not header:
        # Also check the shortcut header injected by Container Apps
        return request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
    principal = _decode_principal(header)
    if principal is None:
        return None
    return _get_claim(principal, _OID_CLAIM) or _get_claim(principal, "sub")


def get_caller_email(request: Request) -> str | None:
    """Return the email/username of the authenticated caller."""
    header = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not header:
        return request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    principal = _decode_principal(header)
    if principal is None:
        return None
    return _get_claim(principal, _PREFERRED_USERNAME_CLAIM)


def has_role(request: Request, role: str) -> bool:
    """Return True if the authenticated caller has the given app role."""
    header = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not header:
        return False
    principal = _decode_principal(header)
    if principal is None:
        return False
    return role in _get_all_claims(principal, _ROLES_CLAIM)


def is_authenticated(request: Request) -> bool:
    """Return True if Easy Auth headers are present (request passed auth layer)."""
    return (
        "X-MS-CLIENT-PRINCIPAL" in request.headers
        or "X-MS-CLIENT-PRINCIPAL-ID" in request.headers
    )
