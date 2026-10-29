from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.revisions import sign_original_input
from app.takeoff.contracts import EstimateInputSnapshot, snapshot_catalog
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import FixtureCount, PlanSchema

client = TestClient(app)
PROJECT = "00000000-0000-0000-0000-000000000001"
REVISION = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def payload(catalog, monkeypatch):
    monkeypatch.setenv("ESTIMATE_REVISIONS_ENABLED", "true")
    # Preserve an unpriced material and unsupported detection as well as inputs.
    catalog = {k: v for k, v in catalog.items() if k != "UTB01"}
    plan = PlanSchema(plan_type="Electrical Plan", source="detection",
                      fixtures=[FixtureCount(item_id="OT01", count=12)])
    params = EstimatingParams()
    estimate = estimate_plan(plan, catalog, params)
    original_input = EstimateInputSnapshot(plan=plan, params=params,
                                           prices=snapshot_catalog(catalog, estimate.priced_at))
    return {
        "project_id": PROJECT,
        "precondition": {"expected_active_revision_id": None, "idempotency_key": REVISION},
        "asset": {"source_sha256": "a" * 64, "original_filename": "plan.png", "media_type": "image/png", "byte_size": 1234},
        "result": {
            "original_input": original_input.model_dump(mode="json"),
            "input_signature": sign_original_input(original_input, "a" * 64, "test-user"),
            "scan": {"source_sha256": "a" * 64, "pipeline_version": "image-v1", "method": "detection"},
            "estimate": estimate.model_dump(), "extraction": None,
            "unmatched_detections": [{"label": "UNKNOWN", "confidence": .8, "bbox": [1, 2, 3, 4], "dimension_text": None}],
        },
    }


def test_save_replays_frozen_prices_and_derives_owner(payload):
    with patch("app.revisions._client") as factory:
        factory.return_value.rpc.return_value.execute.return_value = SimpleNamespace(data=REVISION)
        response = client.post("/api/estimate/revisions", json=payload)
    assert response.status_code == 200, response.text
    assert response.json() == {"revision_id": REVISION}
    name, args = factory.return_value.rpc.call_args.args
    assert name == "save_scan_estimate"
    assert args["p_owner"] == "test-user"  # Dependency, not a browser field.
    assert args["p_result"]["estimate"]["unpriced"] == payload["result"]["estimate"]["unpriced"]
    assert args["p_result"]["unmatched_detections"] == payload["result"]["unmatched_detections"]
    assert args["p_result"]["original_input"] == payload["result"]["original_input"]
    assert args["p_expected_active_revision_id"] is None


@pytest.mark.parametrize("field,value", [("grand_total", 0), ("line_items", []), ("unpriced", []), ("assumptions", [])])
def test_rejects_outputs_that_do_not_reproduce(payload, field, value):
    payload["result"]["estimate"][field] = value
    with patch("app.revisions._client") as factory:
        response = client.post("/api/estimate/revisions", json=payload)
    assert response.status_code == 422
    factory.assert_not_called()


def test_rejects_changed_rules_without_repricing(payload):
    payload["result"]["original_input"]["rules_version"] = "obsolete"
    payload["result"]["estimate"]["rules_version"] = "obsolete"
    assert client.post("/api/estimate/revisions", json=payload).status_code == 409


@pytest.mark.parametrize("change", ["owner", "hash", "asset", "timestamp", "precondition"])
def test_rejects_inconsistent_or_untrusted_fields(payload, change):
    if change == "owner": payload["owner"] = PROJECT
    if change == "hash": payload["result"]["original_input"]["prices"]["items"][0]["price"] += 1
    if change == "asset": payload["asset"]["source_sha256"] = "b" * 64
    if change == "timestamp": payload["result"]["estimate"]["priced_at"] = "bad-date"
    if change == "precondition": del payload["precondition"]["expected_active_revision_id"]
    with patch("app.revisions._client") as factory:
        assert client.post("/api/estimate/revisions", json=payload).status_code == 422
    factory.assert_not_called()


@pytest.mark.parametrize("code,status", [("P0002", 404), ("PT409", 409), ("40001", 409), ("23505", 409), ("22023", 422), ("PGRST202", 503)])
def test_storage_failures_are_actionable_and_do_not_leak_details(payload, code, status):
    with patch("app.revisions._client") as factory:
        factory.return_value.rpc.return_value.execute.side_effect = APIError({"code": code, "message": "private SQL details", "details": None, "hint": None})
        response = client.post("/api/estimate/revisions", json=payload)
    assert response.status_code == status
    assert "private SQL" not in response.text


def test_storage_is_disabled_until_deployed(payload, monkeypatch):
    monkeypatch.delenv("ESTIMATE_REVISIONS_ENABLED")
    with patch("app.revisions._client") as factory:
        assert client.post("/api/estimate/revisions", json=payload).status_code == 503
    factory.assert_not_called()


def test_failure_uses_verified_owner_and_does_not_write_directly(payload):
    with patch("app.revisions._client") as factory:
        factory.return_value.rpc.return_value.execute.return_value = SimpleNamespace(data=None)
        response = client.post("/api/estimate/scan-failure", json={"project_id": PROJECT, "message": "Unreadable plan"})
    assert response.status_code == 200
    assert factory.return_value.rpc.call_args.args == ("record_scan_failure", {
        "p_owner": "test-user", "p_project_id": PROJECT, "p_message": "Unreadable plan",
    })
