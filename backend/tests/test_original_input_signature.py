"""The saved "original read" must be what the scanner produced.

/api/estimate/revisions checks that the estimate reproduces from its inputs,
but the inputs come from the browser. Without a signature, someone could edit
the counts, recompute, and save them; the editor then shows them as the
original read, which R30 promises to keep apart from user-entered values.
/api/estimate/image now signs the original input for this user and image.
"""
import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.auth import current_user
from app.extract.ocr import TextBox
from app.main import app
from app.takeoff.contracts import EstimateInputSnapshot
from app.takeoff.estimator import estimate_plan

client = TestClient(app)
PROJECT = "00000000-0000-0000-0000-000000000001"


def tag(text, x):
    return TextBox(text, x, 40, .9, False, ((x - 5, 35), (x + 5, 35), (x + 5, 45), (x - 5, 45)))


def browser_json(value):
    """JSON as a browser re-sends it: whole-number floats come back as ints."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: browser_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [browser_json(v) for v in value]
    return value


@pytest.fixture
def scanned(catalog, monkeypatch):
    monkeypatch.setenv("ESTIMATE_REVISIONS_ENABLED", "true")
    buffer = io.BytesIO()
    Image.new("RGB", (200, 80), "white").save(buffer, format="PNG")
    raw = buffer.getvalue()
    tags = [tag("WC", 20), tag("WC", 60), tag("LAV", 100), tag("FD", 140)]
    with patch("app.main.read_tiled", return_value=tags), patch("app.main.load_catalog", return_value=catalog):
        response = client.post("/api/estimate/image", files={"file": ("plan.png", raw, "image/png")},
                               data={"plan_type": "Plumbing Plan"})
    assert response.status_code == 200, response.text
    result = browser_json(json.loads(json.dumps(response.json())))
    return {
        "project_id": PROJECT,
        "precondition": {"expected_active_revision_id": None, "idempotency_key": "00000000-0000-0000-0000-000000000002"},
        "result": result,
        "asset": {"source_sha256": result["scan"]["source_sha256"], "original_filename": "plan.png",
                  "media_type": "image/png", "byte_size": len(raw)},
    }


def save(payload):
    with patch("app.revisions._client") as factory:
        factory.return_value.rpc.return_value.execute.return_value = SimpleNamespace(data="rev")
        response = client.post("/api/estimate/revisions", json=payload)
    return response, factory


def test_a_scan_result_saved_unchanged_is_accepted(scanned):
    assert scanned["result"]["input_signature"]
    response, _ = save(scanned)
    assert response.status_code == 200, response.text


def test_an_edited_original_is_refused_even_when_its_estimate_reproduces(scanned):
    snapshot = EstimateInputSnapshot.model_validate(scanned["result"]["original_input"])
    snapshot.plan.fixture_tags["water_closet"] = 9
    estimate = estimate_plan(snapshot.plan, snapshot.prices.to_catalog(), snapshot.params)
    estimate.priced_at = scanned["result"]["estimate"]["priced_at"]
    scanned["result"]["original_input"] = snapshot.model_dump(mode="json")
    scanned["result"]["estimate"] = estimate.model_dump(mode="json")
    response, factory = save(scanned)
    assert response.status_code == 422
    assert "Rescan" in response.json()["detail"]
    factory.assert_not_called()


def test_a_result_signed_for_another_user_is_refused(scanned):
    app.dependency_overrides[current_user] = lambda: "someone-else"
    try:
        response, factory = save(scanned)
    finally:
        app.dependency_overrides[current_user] = lambda: "test-user"
    assert response.status_code == 422
    factory.assert_not_called()


def test_a_result_with_no_signature_is_refused(scanned):
    scanned["result"].pop("input_signature")
    response, factory = save(scanned)
    assert response.status_code == 422
    factory.assert_not_called()
