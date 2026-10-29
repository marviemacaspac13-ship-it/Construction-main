"""Every database call shares one Supabase client and its open connection.

`_client()` used to build a new client - and a new HTTPS connection - per call,
so one plan upload opened three. The sign-in check already cached its own.
"""
from unittest.mock import patch

import pytest

from app import materials


@pytest.fixture
def fresh_cache():
    clear = getattr(materials._client, "cache_clear", lambda: None)
    clear()
    yield
    clear()  # never leave a fake client behind for other tests


def test_database_calls_share_one_client(monkeypatch, fresh_cache):
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "not-a-real-key")
    with patch("app.materials.create_client", side_effect=lambda url, key: object()) as create:
        assert materials._client() is materials._client()
    assert create.call_count == 1


def test_missing_settings_are_reported_every_time(monkeypatch, fresh_cache):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    for _ in range(2):  # a failure is not remembered as a client
        with pytest.raises(RuntimeError):
            materials._client()
