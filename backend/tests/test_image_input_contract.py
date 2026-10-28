"""The API retains source inputs, not just their derived material lines."""

import hashlib
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Detection
from app.takeoff.contracts import EstimateInputSnapshot
from app.takeoff.estimator import estimate_plan
from app.takeoff.schema import FixtureCount, PlanSchema, Wall

client = TestClient(app)
PNG = (Path(__file__).parent / "fixtures" / "plans" / "01.png").read_bytes()


@pytest.mark.parametrize("plan, reader, result", [
    (PlanSchema(plan_type="Floor Plan", source="ocr", walls=[Wall(id="w", length_m=12)]),
     "_read_plan", lambda plan: (plan, None)),
    (PlanSchema(plan_type="Electrical Plan", source="detection",
                fixtures=[FixtureCount(item_id="OT01", count=12)]),
     "_detect_plan", lambda plan: (plan, None, [])),
    (PlanSchema(plan_type="Plumbing Plan", source="tags",
                fixture_tags={"water_closet": 3, "lavatory": 2, "cleanout": 1}),
     "_read_plumbing", lambda plan: (plan, None)),
])
def test_every_image_path_returns_replayable_inputs(plan, reader, result, catalog):
    raw = PNG
    with patch(f"app.main.{reader}", return_value=result(plan)), \
         patch("app.main.load_catalog", return_value=catalog):
        response = client.post(
            "/api/estimate/image", files={"file": ("plan.png", raw, "image/png")},
            data={"plan_type": plan.plan_type},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    saved = EstimateInputSnapshot.model_validate(body["original_input"])
    assert saved.plan == plan
    assert saved.rules_version == body["estimate"]["rules_version"]
    assert saved.params.default_wall_height_m == 2.7
    assert body["scan"] == {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "pipeline_version": "image-v1", "method": plan.source,
    }
    replay = estimate_plan(saved.plan, saved.prices.to_catalog(), saved.params)
    assert replay.grand_total == body["estimate"]["grand_total"]
    assert [line.model_dump() for line in replay.line_items] == body["estimate"]["line_items"]
    assert body["unmatched_detections"] == []


def test_mixed_electrical_scan_preserves_unknown_hits_and_unpriced_materials(catalog):
    incomplete_catalog = {key: row for key, row in catalog.items() if key != "UTB01"}
    unknown = Detection(label="NOT_A_SKU", confidence=0.8, bbox=[80, 80, 90, 90])
    detections = [
        Detection(label="OT01", confidence=0.9, bbox=[i, i, i + 1, i + 1])
        for i in range(12)
    ] + [unknown]
    with patch("app.main.load_catalog", return_value=incomplete_catalog), \
         patch("app.templates_store.list_templates", return_value={"OT01": ["a.png"]}), \
         patch("app.main.preprocess_image", return_value=np.zeros((100, 100, 3), np.uint8)), \
         patch("app.main.match_templates", return_value=detections):
        response = client.post(
            "/api/estimate/image", files={"file": ("plan.png", PNG, "image/png")},
            data={"plan_type": "Electrical Plan"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["original_input"]["plan"]["fixtures"] == [{"item_id": "OT01", "count": 12}]
    assert body["unmatched_detections"] == [unknown.model_dump()]
    unpriced = body["estimate"]["unpriced"]
    assert len(unpriced) == 1
    assert unpriced[0]["item_id"] == "UTB01"
    assert unpriced[0]["quantity"] == 12
    assert unpriced[0]["rule"] == "electrical.utility_boxes"
