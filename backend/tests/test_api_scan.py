"""The /api/scan guard.

An empty templates store cannot match anything, so the endpoint must say so
rather than return a zero-peso estimate with HTTP 200 - which looks exactly
like a successful scan of a plan containing no materials.
"""

from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PNG = b"fake png bytes"


@pytest.fixture(autouse=True)
def stub_catalog(catalog):
    with patch("app.main.load_catalog", return_value=catalog):
        yield


def test_no_templates_uploaded_is_reported_not_silently_zero():
    with patch("app.templates_store.list_templates", return_value={}):
        res = client.post(
            "/api/scan", files={"file": ("plan.png", PNG, "image/png")}
        )
    assert res.status_code == 422
    assert "Symbol Library" in res.json()["detail"]


def test_templates_present_but_nothing_matched_is_a_real_empty_result():
    """Zero matches AFTER references exist is a legitimate 200."""
    with patch("app.templates_store.list_templates", return_value={"CHB01": ["a.png"]}), \
         patch("app.main.preprocess_image", return_value=np.zeros((10, 10, 3), np.uint8)), \
         patch("app.main.match_templates", return_value=[]):
        res = client.post(
            "/api/scan", files={"file": ("plan.png", PNG, "image/png")}
        )
    assert res.status_code == 200
    body = res.json()
    assert body["line_items"] == []
    assert body["grand_total"] == 0.0


def test_non_image_is_still_rejected_first():
    res = client.post("/api/scan", files={"file": ("notes.txt", b"hi", "text/plain")})
    assert res.status_code == 400