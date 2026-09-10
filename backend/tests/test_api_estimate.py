"""The two estimate endpoints.

Supabase is stubbed with the committed catalog snapshot so these run
offline. The image test is marked `ocr` because it runs the real reader
over a real plan.
"""

from pathlib import Path
from unittest.mock import patch

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
    # Openings are not read on this plan, and that must be stated.
    assert any("over-estimated" in w for w in ex["warnings"])

    est = body["estimate"]
    assert est["grand_total"] == pytest.approx(121189.74)
    assert est["unpriced"] == []
    assert {li["item_id"] for li in est["line_items"]} >= {
        "CHB01", "CHB02", "CMT01", "SND02", "DB01", "GI01"
    }