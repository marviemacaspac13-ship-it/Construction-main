"""Every API route but /health refuses a caller with no valid session.

Until Sep 2026 all eight routes were open (audit finding API-02), including
the one that deletes symbol crops. These run the REAL dependency, with
Supabase's answer stubbed, so they check the gate itself rather than the
stand-in every other test uses.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from supabase_auth.errors import AuthApiError

from app.main import app

pytestmark = pytest.mark.real_auth

client = TestClient(app)

GUARDED = [
    ("post", "/api/scan"),
    ("get", "/api/materials"),
    ("post", "/api/templates"),
    ("get", "/api/templates"),
    ("delete", "/api/templates/OT01/x.png"),
    ("post", "/api/estimate"),
    ("post", "/api/estimate/image"),
]


def _supabase_says(user=None, raises=None):
    auth = SimpleNamespace()
    if raises is not None:
        def get_user(token):
            raise raises
    else:
        def get_user(token):
            return SimpleNamespace(user=user)
    auth.get_user = get_user
    return patch("app.auth._auth_client", return_value=SimpleNamespace(auth=auth))


def test_every_api_route_is_guarded():
    """A route added without the guard shows up here, not in production."""
    api = {
        (m.lower(), r.path)
        for r in app.routes
        if getattr(r, "path", "").startswith("/api/")
        for m in r.methods
    }
    guarded = {(m, p.replace("OT01/x.png", "{item_id}/{filename}")) for m, p in GUARDED}
    assert api == guarded


@pytest.mark.parametrize("method,path", GUARDED)
def test_no_session_is_refused(method, path):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("header", ["", "Bearer", "Bearer   ", "Basic abc", "token-without-scheme"])
def test_a_malformed_header_is_refused_without_asking_supabase(header):
    with patch("app.auth._auth_client", side_effect=AssertionError("must not be called")):
        assert client.get("/api/templates", headers={"Authorization": header}).status_code == 401


def test_a_token_supabase_rejects_is_refused():
    with _supabase_says(raises=AuthApiError("invalid JWT", 401, None)):
        r = client.get("/api/templates", headers={"Authorization": "Bearer forged"})
    assert r.status_code == 401


def test_a_token_with_no_user_is_refused():
    with _supabase_says(user=None):
        r = client.get("/api/templates", headers={"Authorization": "Bearer stale"})
    assert r.status_code == 401


def test_supabase_down_is_a_503_not_a_sign_out():
    """A network blip must not look like an expired session to the browser."""
    with _supabase_says(raises=ConnectionError("unreachable")):
        r = client.get("/api/templates", headers={"Authorization": "Bearer fine"})
    assert r.status_code == 503


def test_a_valid_session_gets_through():
    with _supabase_says(user=SimpleNamespace(id="user-1")):
        r = client.get("/api/templates", headers={"Authorization": "Bearer good"})
    assert r.status_code == 200


def test_health_stays_open():
    assert client.get("/health").status_code == 200
