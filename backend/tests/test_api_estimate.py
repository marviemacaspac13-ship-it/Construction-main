"""The two estimate endpoints.

Supabase is stubbed with the committed catalog snapshot so these run
offline. The image test is marked `ocr` because it runs the real reader
over a real plan.
"""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

PLANS = Path(__file__).resolve().parent / "fixtures" / "plans"
client = TestClient(app)


@pytest.fixture(autouse=True)
def stub_catalog(catalog):
    with patch("app.main.load_catalog", return_value=catalog):
        yield


# --- POST /api/estimate (structured input) -------------------------------

def test_estimate_prices_a_structured_plan():
    body = {
        "plan": {
            "plan_type": "Floor Plan",
            "walls": [{"id": "w1", "length_m": 10.0, "height_m": 3.0, "thickness": "6in"}],
        }
    }
    res = client.post("/api/estimate", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["plan_type"] == "Floor Plan"
    assert data["rules_version"]
    assert data["grand_total"] > 0
    chb = next(li for li in data["line_items"] if li["item_id"] == "CHB02")
    assert chb["quantity"] == 394  # ceil(30 m2 * 12.5 * 1.05)


def test_estimate_honours_param_overrides():
    body = {
        "plan": {"plan_type": "Floor Plan", "walls": [{"id": "w1", "length_m": 10.0}]},
        "params": {"default_wall_height_m": 2.5},
    }
    data = client.post("/api/estimate", json=body).json()
    chb = next(li for li in data["line_items"] if li["item_id"] == "CHB02")
    assert chb["quantity"] == 329  # ceil(25 m2 * 12.5 * 1.05)


def test_estimate_returns_the_derivation_for_audit():
    body = {
        "plan": {
            "plan_type": "Floor Plan",
            "walls": [{"id": "w1", "length_m": 10.0, "height_m": 3.0}],
        }
    }
    data = client.post("/api/estimate", json=body).json()
    chb = next(li for li in data["line_items"] if li["item_id"] == "CHB02")
    assert "12.5 pcs/m^2" in chb["derivation"]
    assert data["assumptions"]


def test_unknown_plan_type_is_rejected():
    res = client.post("/api/estimate", json={"plan": {"plan_type": "Landscape Plan"}})
    assert res.status_code == 422


# --- POST /api/estimate/image -------------------------------------------

def test_non_image_upload_is_rejected():
    res = client.post(
        "/api/estimate/image",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400


def test_electrical_plan_is_refused_rather_than_guessed():
    """The reader only understands floor plans; it must say so, not invent."""
    res = client.post(
        "/api/estimate/image",
        files={"file": ("plan.png", b"x", "image/png")},
        data={"plan_type": "Electrical Plan"},
    )
    assert res.status_code == 422
    assert "Symbol Library" in res.json()["detail"]


def test_undecodable_image_is_rejected():
    res = client.post(
        "/api/estimate/image",
        files={"file": ("plan.png", b"not really a png", "image/png")},
    )
    assert res.status_code == 400


@pytest.mark.ocr
@pytest.mark.skipif(not (PLANS / "01.png").exists(), reason="plan images not present")
def test_real_plan_image_prices_end_to_end():
    with open(PLANS / "01.png", "rb") as fh:
        res = client.post(
            "/api/estimate/image",
            files={"file": ("01.png", fh.read(), "image/png")},
            data={"plan_type": "Floor Plan"},
        )
    assert res.status_code == 200, res.text
    body = res.json()

    ex = body["extraction"]
    assert ex["unit"] == "mm"
    assert (ex["envelope_w_m"], ex["envelope_l_m"]) == (14.0, 11.0)
    assert len(ex["rooms"]) == 10
    assert ex["total_wall_m"] == pytest.approx(91.9)
    assert ex["confidence"] >= 0.9
    assert all(c["ok"] for c in ex["chains"])
    # Openings could not be read, so they are assumed - and stated as assumed.
    assert any("assumed from" in w for w in ex["warnings"])
    assert ex["doors"] == 10 and ex["windows"] == 10

    # Concrete is derived from the envelope, never read, and says so.
    assert ex["column_count"] == 15
    assert ex["concrete_volume_m3"] == pytest.approx(19.12)
    assert any("Concrete is assumed, not read" in w for w in ex["warnings"])

    est = body["estimate"]
    assert est["grand_total"] == pytest.approx(210003.30)
    assert est["unpriced"] == []
    assert {li["item_id"] for li in est["line_items"]} >= {
        "CHB01", "CHB02", "CMT01", "SND02", "DB01", "GI01",
        "GVF01",  # gravel reaches an estimate only through concrete
    }
    assert any("Structural frame assumed" in a for a in est["assumptions"])

# --- POST /api/estimate/image, detection path ---------------------------

def test_electrical_plan_is_refused_when_no_references_exist():
    """Refusing is right when nothing could possibly match."""
    with patch("app.templates_store.list_templates", return_value={}):
        res = client.post(
            "/api/estimate/image",
            files={"file": ("plan.png", b"x", "image/png")},
            data={"plan_type": "Electrical Plan"},
        )
    assert res.status_code == 422
    assert "Symbol Library" in res.json()["detail"]


def test_electrical_plan_is_priced_from_detections_when_references_exist():
    """The whole point of Task 13: this plan type can now be estimated."""
    from app.schemas import Detection

    detections = [
        Detection(label="OT01", confidence=0.9, bbox=[0, 0, 1, 1]),
        Detection(label="OT01", confidence=0.9, bbox=[2, 2, 3, 3]),
        Detection(label="SW01", confidence=0.8, bbox=[4, 4, 5, 5]),
    ]
    with patch("app.templates_store.list_templates", return_value={"OT01": ["a.png"]}), \
         patch("app.main.preprocess_image", return_value=np.zeros((10, 10, 3), np.uint8)), \
         patch("app.main.match_templates", return_value=detections):
        res = client.post(
            "/api/estimate/image",
            files={"file": ("plan.png", b"x", "image/png")},
            data={"plan_type": "Electrical Plan"},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    # Nothing was "read", so there is no read-quality report.
    assert body["extraction"] is None
    est = body["estimate"]
    assert est["plan_type"] == "Electrical Plan"
    by_sku = {li["item_id"]: li["quantity"] for li in est["line_items"]}
    assert by_sku["OT01"] == 2
    assert by_sku["SW01"] == 1
    assert by_sku["UTB01"] == 3  # one utility box per wiring device
    assert est["grand_total"] > 0


def test_plumbing_plan_is_priced_from_detections():
    from app.schemas import Detection

    detections = [Detection(label="PVTB01", confidence=0.9, bbox=[0, 0, 1, 1])] * 4
    with patch("app.templates_store.list_templates", return_value={"PVTB01": ["a.png"]}), \
         patch("app.main.preprocess_image", return_value=np.zeros((10, 10, 3), np.uint8)), \
         patch("app.main.match_templates", return_value=detections):
        res = client.post(
            "/api/estimate/image",
            files={"file": ("plan.png", b"x", "image/png")},
            data={"plan_type": "Plumbing Plan"},
        )
    assert res.status_code == 200, res.text
    est = res.json()["estimate"]
    assert {li["item_id"]: li["quantity"] for li in est["line_items"]}["PVTB01"] == 4


def test_an_unknown_plan_type_is_rejected():
    res = client.post(
        "/api/estimate/image",
        files={"file": ("plan.png", b"x", "image/png")},
        data={"plan_type": "Landscape Plan"},
    )
    assert res.status_code == 422
    assert "Unknown plan type" in res.json()["detail"]