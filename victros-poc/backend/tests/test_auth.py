"""Tests for server/auth.py — Easy Auth header parsing.

AU-01  get_caller_user_id returns None when no headers present (local dev)
AU-02  get_caller_user_id reads X-MS-CLIENT-PRINCIPAL-ID shortcut header
AU-03  get_caller_user_id decodes X-MS-CLIENT-PRINCIPAL and extracts oid claim
AU-04  get_caller_user_id falls back to sub when oid absent
AU-05  get_caller_email returns None when no headers present
AU-06  get_caller_email decodes preferred_username from principal header
AU-07  has_role returns False when no principal header
AU-08  has_role returns True when role is present in claims
AU-09  has_role returns False when role is absent from claims
AU-10  is_authenticated returns False with no headers
AU-11  is_authenticated returns True with X-MS-CLIENT-PRINCIPAL header
AU-12  is_authenticated returns True with X-MS-CLIENT-PRINCIPAL-ID shortcut
AU-13  malformed base64 principal header is handled gracefully (no crash)
"""
from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from server.auth import (
    SNAPSHOT_ADMIN_ROLE,
    get_caller_email,
    get_caller_user_id,
    has_role,
    is_authenticated,
)


def _make_principal(claims: list[dict]) -> str:
    """Encode a principal payload as Container Apps Easy Auth would."""
    payload = {"auth_typ": "aad", "claims": claims}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _mock_request(headers: dict) -> Request:
    """Build a minimal FastAPI Request with the given headers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


# ---------------------------------------------------------------------------
# get_caller_user_id
# ---------------------------------------------------------------------------

def test_au01_no_headers_returns_none():
    req = _mock_request({})
    assert get_caller_user_id(req) is None


def test_au02_shortcut_header():
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL-ID": "user-obj-id-123"})
    assert get_caller_user_id(req) == "user-obj-id-123"


def test_au03_principal_header_oid():
    principal = _make_principal([
        {"typ": "oid", "val": "oid-abc"},
        {"typ": "preferred_username", "val": "user@example.com"},
    ])
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL": principal})
    assert get_caller_user_id(req) == "oid-abc"


def test_au04_falls_back_to_sub():
    principal = _make_principal([
        {"typ": "sub", "val": "sub-xyz"},
    ])
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL": principal})
    assert get_caller_user_id(req) == "sub-xyz"


# ---------------------------------------------------------------------------
# get_caller_email
# ---------------------------------------------------------------------------

def test_au05_no_headers_email_returns_none():
    req = _mock_request({})
    assert get_caller_email(req) is None


def test_au06_email_from_principal():
    principal = _make_principal([
        {"typ": "preferred_username", "val": "alice@example.com"},
    ])
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL": principal})
    assert get_caller_email(req) == "alice@example.com"


# ---------------------------------------------------------------------------
# has_role
# ---------------------------------------------------------------------------

def test_au07_no_header_has_role_false():
    req = _mock_request({})
    assert has_role(req, SNAPSHOT_ADMIN_ROLE) is False


def test_au08_role_present():
    principal = _make_principal([
        {"typ": "roles", "val": SNAPSHOT_ADMIN_ROLE},
        {"typ": "roles", "val": "other.role"},
    ])
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL": principal})
    assert has_role(req, SNAPSHOT_ADMIN_ROLE) is True


def test_au09_role_absent():
    principal = _make_principal([
        {"typ": "roles", "val": "other.role"},
    ])
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL": principal})
    assert has_role(req, SNAPSHOT_ADMIN_ROLE) is False


# ---------------------------------------------------------------------------
# is_authenticated
# ---------------------------------------------------------------------------

def test_au10_not_authenticated():
    req = _mock_request({})
    assert is_authenticated(req) is False


def test_au11_authenticated_via_principal():
    principal = _make_principal([{"typ": "oid", "val": "x"}])
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL": principal})
    assert is_authenticated(req) is True


def test_au12_authenticated_via_shortcut():
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL-ID": "some-id"})
    assert is_authenticated(req) is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_au13_malformed_principal_no_crash():
    req = _mock_request({"X-MS-CLIENT-PRINCIPAL": "!!!not-valid-base64!!!"})
    # Should return None gracefully, not raise
    assert get_caller_user_id(req) is None
    assert get_caller_email(req) is None
    assert has_role(req, SNAPSHOT_ADMIN_ROLE) is False
