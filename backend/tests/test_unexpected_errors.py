"""An error nothing else caught reaches the browser as a fixed message.

The catch-all handler used to send `str(exc)`, so a missing catalog item
reached the user as `'PDP03'` and a network failure could carry the Supabase
project address. The traceback still goes to the server log.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_unexpected_error_hides_its_internals():
    leak = RuntimeError("connect failed: https://abcdefghijklmnopqrst.supabase.co/rest/v1/materials")
    with patch("app.main.load_catalog", side_effect=leak):
        response = client.get("/api/materials")
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "supabase" not in detail.lower()
    assert "connect failed" not in detail
    assert "Try again" in detail
    # The browser still has to be allowed to read the error.
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
