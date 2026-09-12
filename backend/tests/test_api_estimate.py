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


def test_electrical_plan_is_refused_when_the_library_is_empty():
    """With no references nothing can match, and a zero-peso 200 would lie.

    The library is populated now, so this has to empty it explicitly - it
    used to pass by accident because no crops existed anywhere.
    """
    with patch("app.templates_store.list_templates", return_value={}):
        res = client.post(
            "/api/estimate/image",
            files={"file": ("plan.png", b"x", "image/png")},
            data={"plan_type": "Electrical Plan"},
        )
    assert res.status_code == 422
    assert "Symbol Library" in res.json()["detail"]


def test_the_library_guard_is_per_trade():
    """Asking whether ANY template exists is not enough.

    Once electrical crops were installed, a plan of another trade sailed
    past the guard and returned a cheerful 200 with a zero-peso estimate -
    exactly the "successful scan of a plan with no materials on it" the
    guard exists to prevent. Plumbing no longer goes through templates at
    all, so this is checked with the library emptied instead.
    """
    with patch("app.main._templates_for", return_value={}):
        res = client.post(
            "/api/estimate/image",
            files={"file": ("plan.png", b"x", "image/png")},
            data={"plan_type": "Electrical Plan"},
        )
    assert res.status_code == 422
    assert "Symbol Library" in res.json()["detail"]


def test_a_plan_where_nothing_matched_is_refused_not_priced_at_zero():
    """Zero matches is a failed read, never a real zero.

    Every electrical plan has electrics - that is what makes it one. An
    earlier version returned 200 with a zero-peso estimate here, and six of
    the eleven sample electrical plans came back as cheerful zeroes reading
    as "this building needs no wiring".
    """
    with patch("app.main.match_templates", return_value=[]):
        with open(PLANS / "05.png", "rb") as fh:
            res = client.post(
                "/api/estimate/image",
                files={"file": ("05.png", fh.read(), "image/png")},
                data={"plan_type": "Electrical Plan"},
            )
    assert res.status_code == 422
    assert "nothing to price" in res.json()["detail"]["message"]


def test_detections_that_match_no_catalog_item_are_also_refused():
    """A label with no UnitSpec is dropped, which can empty the plan."""
    from app.schemas import Detection

    junk = [Detection(label="NOT_A_SKU", confidence=0.9, bbox=[0, 0, 8, 8])]
    with patch("app.main.match_templates", return_value=junk):
        with open(PLANS / "05.png", "rb") as fh:
            res = client.post(
                "/api/estimate/image",
                files={"file": ("05.png", fh.read(), "image/png")},
                data={"plan_type": "Electrical Plan"},
            )
    assert res.status_code == 422


def test_an_electrical_plan_prices_once_references_exist():
    """The counterpart: the same route succeeds against the real library."""
    with open(PLANS / "05.png", "rb") as fh:
        res = client.post(
            "/api/estimate/image",
            files={"file": ("05.png", fh.read(), "image/png")},
            data={"plan_type": "Electrical Plan"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    # Nothing was READ on this path, so there is nothing to report on.
    assert body["extraction"] is None
    assert body["estimate"]["grand_total"] > 0


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
    assert ex["concrete_volume_m3"] == pytest.approx(26.66, abs=0.01)
    assert any("Concrete is assumed, not read" in w for w in ex["warnings"])

    est = body["estimate"]
    assert est["grand_total"] == pytest.approx(308356.26, abs=0.01)
    assert est["unpriced"] == []
    assert {li["item_id"] for li in est["line_items"]} >= {
        "CHB01", "CHB02", "CMT01", "SND02", "DB01", "GI01",
        "GVF01",  # gravel reaches an estimate only through concrete
        "DB03",   # 16mm is the guide main bar for columns, beams and footings
    }
    assert any("follow the project guide" in a for a in est["assumptions"])
    assert any("still assumed" in a for a in est["assumptions"])
    # Slab mesh and CHB wall bars are both DB01 and must be one purchase.
    assert len([li for li in est["line_items"] if li["item_id"] == "DB01"]) == 1

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


def test_a_plumbing_plan_is_read_not_detected():
    """Plumbing takes the tag-reading path, never template matching.

    The countable things on a sanitary plan are written beside the fixture,
    not drawn, so there is nothing to match. A stub asserts the routing:
    if this ever went through match_templates again it would need a symbol
    library that cannot exist.
    """
    with patch("app.main.match_templates") as detector,          patch("app.main.read_tiled", return_value=[]),          patch("app.main.tally", return_value={"water_closet": 3, "lavatory": 2}):
        with open(PLANS / "07.png", "rb") as fh:
            res = client.post(
                "/api/estimate/image",
                files={"file": ("07.png", fh.read(), "image/png")},
                data={"plan_type": "Plumbing Plan"},
            )
    detector.assert_not_called()
    assert res.status_code == 200, res.text

    est = res.json()["estimate"]
    by_item = {li["item_id"]: li["quantity"] for li in est["line_items"]}
    # 3 water closets pull 4in drain and its wye; 2 lavatories pull 2in.
    assert by_item["PVYO03"] == 3
    assert by_item["PVYO01"] == 2
    # The fixtures themselves are client-supplied and never priced.
    assert not any(k.startswith("PF") for k in by_item)
    assert any("counted but not priced" in a for a in est["assumptions"])


def test_a_plumbing_plan_with_no_readable_tags_is_refused():
    """A zero-peso 200 would read as "this plan needs no pipework"."""
    with patch("app.main.read_tiled", return_value=[]),          patch("app.main.tally", return_value={}):
        with open(PLANS / "07.png", "rb") as fh:
            res = client.post(
                "/api/estimate/image",
                files={"file": ("07.png", fh.read(), "image/png")},
                data={"plan_type": "Plumbing Plan"},
            )
    assert res.status_code == 422
    assert "higher-resolution" in res.json()["detail"]["message"]


def test_an_unknown_plan_type_is_rejected():
    res = client.post(
        "/api/estimate/image",
        files={"file": ("plan.png", b"x", "image/png")},
        data={"plan_type": "Landscape Plan"},
    )
    assert res.status_code == 422
    assert "Unknown plan type" in res.json()["detail"]