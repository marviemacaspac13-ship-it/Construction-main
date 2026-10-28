"""Project price edits must not change source quantities or leak into the catalog."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.takeoff.contracts import (
    EstimateCorrections, EstimateInputSnapshot, EstimateRevision, PriceSnapshot, snapshot_catalog,
)
from app.takeoff.corrections import recalculate
from app.takeoff.estimator import estimate_plan
from app.takeoff.frame import derive_frame
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import FixtureCount, PlanSchema, Wall


@pytest.fixture
def original(catalog):
    params = EstimatingParams()
    return EstimateInputSnapshot(
        plan=PlanSchema(plan_type="Floor Plan", walls=[Wall(id="w", length_m=10)],
                        concrete=derive_frame(10, 12, params).elements),
        params=params, prices=snapshot_catalog(catalog, "2026-10-11T00:00:00Z"),
    )


def edit(original, prices=None, quantities=None):
    return recalculate(original, EstimateCorrections(unit_prices=prices or {}, quantities=quantities or {}))


def lines(result):
    return {line.item_id: line for line in result.estimate.line_items}


def test_price_only_edit_changes_money_not_quantities_or_derivations(original):
    before = edit(original)
    after = edit(original, {"CMT01":300, "DB01":175.25})
    assert after.effective_input.plan == before.effective_input.plan
    assert after.effective_input.params == before.effective_input.params
    assert after.estimate.unpriced == before.estimate.unpriced
    assert after.estimate.assumptions == before.estimate.assumptions
    money = {"unit_price", "line_total"}
    for item_id, old in lines(before).items():
        new = lines(after)[item_id]
        assert new.model_dump(exclude=money) == old.model_dump(exclude=money)
        price = {"CMT01":300, "DB01":175.25}.get(item_id, old.unit_price)
        assert new.unit_price == price
        assert new.line_total == round(old.quantity * price, 2)
    assert after.estimate.grand_total == round(sum(li.line_total for li in lines(after).values()), 2)


def test_original_prices_metadata_units_and_shared_catalog_are_preserved(original, catalog):
    snapshot_before, catalog_before = original.model_dump_json(), deepcopy(catalog)
    result = edit(original, {"CMT01":0, "DB01":170})
    effective = result.effective_input.prices
    assert original.model_dump_json() == snapshot_before
    assert catalog == catalog_before
    assert effective.snapshot_id != original.prices.snapshot_id
    assert effective.captured_at == original.prices.captured_at
    assert effective.currency == "PHP"
    for old, new in zip(original.prices.items, effective.items):
        assert new.model_dump(exclude={"price"}) == old.model_dump(exclude={"price"})
    assert PriceSnapshot.model_validate_json(effective.model_dump_json()) == effective


def test_two_project_drafts_do_not_share_mutable_prices(original):
    # Two projects can start from the exact same snapshot object.
    project_a = edit(original, {"CMT01":300})
    project_b = edit(original, {"CMT01":400})
    unchanged = edit(original)
    assert lines(project_a)["CMT01"].unit_price == 300
    assert lines(project_b)["CMT01"].unit_price == 400
    assert lines(unchanged)["CMT01"].unit_price == 261
    project_a.effective_input.prices.items[0].price = 999
    assert project_a.effective_input.prices.items[0].price != project_b.effective_input.prices.items[0].price
    assert original.prices.items[0].price == unchanged.effective_input.prices.items[0].price


def test_reset_prices_retains_quantity_corrections_and_restores_base_prices(original):
    quantities = {"wall_height_m":3.2, "slab_area_m2":80, "column_count":12}
    changed = edit(original, {"CMT01":300, "DB01":170}, quantities)
    partial_reset = edit(original, {"DB01":170}, quantities)
    reset = edit(original, {}, quantities)
    assert changed.effective_input.plan == reset.effective_input.plan
    assert changed.effective_input.params == reset.effective_input.params
    assert lines(partial_reset)["CMT01"].unit_price == 261
    assert lines(partial_reset)["DB01"].unit_price == 170
    assert reset.effective_input.prices == original.prices
    expected = estimate_plan(reset.effective_input.plan, original.prices.to_catalog(), reset.effective_input.params)
    assert expected.line_items == reset.estimate.line_items


def test_zero_price_retains_purchase_quantity_and_is_not_unpriced(original):
    before = edit(original)
    after = edit(original, {"CMT01":0})
    cement = lines(after)["CMT01"]
    assert cement.quantity == lines(before)["CMT01"].quantity > 0
    assert cement.unit_price == cement.line_total == 0
    assert not any(li.item_id == "CMT01" for li in after.estimate.unpriced)
    assert after.estimate.grand_total == pytest.approx(before.estimate.grand_total - lines(before)["CMT01"].line_total)


def test_missing_catalog_row_remains_unpriced_and_cannot_be_invented(original):
    catalog = original.prices.to_catalog()
    del catalog["CMT01"]
    original.prices = snapshot_catalog(catalog, "2026-10-11T00:00:00Z")
    before = edit(original)
    after = edit(original, {"DB01":170})
    assert after.estimate.unpriced == before.estimate.unpriced
    assert any(li.item_id == "CMT01" for li in after.estimate.unpriced)
    with pytest.raises(ValueError, match="missing from the captured catalog"):
        edit(original, {"CMT01":300})


def test_unused_supported_sku_override_can_be_used_by_later_count_edit(original):
    original.plan = PlanSchema(plan_type="Electrical Plan", fixtures=[FixtureCount(item_id="OT01", count=12)])
    result = edit(original, {"OT02":50}, {"electrical_counts":{"OT02":3}})
    assert lines(result)["OT02"].quantity == 3
    assert lines(result)["OT02"].line_total == 150
    price_only = edit(original, {"OT02":50})
    assert "OT02" not in lines(price_only)
    assert price_only.estimate.grand_total == edit(original).estimate.grand_total


def test_reopened_serialized_revision_replays_after_live_catalog_changes(original, catalog, tmp_path):
    result = edit(original, {"CMT01":0, "DB01":170}, {"slab_area_m2":80})
    revision = EstimateRevision(
        id=uuid4(), scan_revision_id=uuid4(), created_by=uuid4(), created_at=datetime.now(timezone.utc),
        corrections=result.corrections, effective_input=result.effective_input, estimate=result.estimate,
    )
    path = tmp_path / "revision.json"
    path.write_text(json.dumps({"original_input":original.model_dump(mode="json"),
                                "revision":revision.model_dump(mode="json")}), encoding="utf-8")
    changed_catalog = deepcopy(catalog)
    for row in changed_catalog.values():
        row["price"] *= 3
    data = json.loads(path.read_text(encoding="utf-8"))
    reopened = EstimateRevision.model_validate(data["revision"])
    base = EstimateInputSnapshot.model_validate(data["original_input"])
    # Replay effective inputs or rebuild from original + corrections: both agree.
    replay = estimate_plan(reopened.effective_input.plan, reopened.effective_input.prices.to_catalog(),
                           reopened.effective_input.params)
    assert estimate_plan(reopened.effective_input.plan, changed_catalog,
                         reopened.effective_input.params).grand_total != replay.grand_total
    rebuilt = recalculate(base, reopened.corrections)
    assert replay.model_dump(exclude={"priced_at"}) == reopened.estimate.model_dump(exclude={"priced_at"})
    assert rebuilt.effective_input == reopened.effective_input
    assert rebuilt.estimate.line_items == reopened.estimate.line_items
    assert edit(base).effective_input.prices == original.prices


def test_price_hash_is_stable_for_same_override_independent_of_order(original):
    a = edit(original, {"CMT01":300, "DB01":170})
    b = edit(original, {"DB01":170, "CMT01":300})
    assert a.effective_input.prices == b.effective_input.prices
    same = edit(original, {"CMT01":261})
    assert same.effective_input.prices.snapshot_id == original.prices.snapshot_id
    assert same.corrections.unit_prices == {"CMT01":261}


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf"), -float("inf"), True, "300", None])
def test_invalid_price_values_rejected(original, price):
    with pytest.raises(ValidationError):
        edit(original, {"CMT01":price})


def test_unknown_sku_rejected(original):
    with pytest.raises(ValidationError, match="unsupported price"):
        edit(original, {"UNKNOWN":100})


def test_fractional_price_uses_existing_line_rounding(original):
    result = edit(original, {"SND02":1234.567})
    line = lines(result)["SND02"]
    assert line.line_total == round(line.quantity * 1234.567, 2)
    assert result.estimate.grand_total == round(sum(li.line_total for li in result.estimate.line_items), 2)


def test_api_prices_without_live_catalog_or_storage_and_records_override(original):
    payload = {"original_input":original.model_dump(mode="json"),
               "corrections":{"unit_prices":{"CMT01":300}, "reason":"Supplier quotation"}}
    with patch("app.materials._client", side_effect=AssertionError("no database")), \
         patch("app.main.load_catalog", side_effect=AssertionError("no live catalog")), \
         patch("app.corrections.audit.record_estimate") as audit:
        response = TestClient(app).post("/api/estimate/recalculate", json=payload)
    assert response.status_code == 200, response.text
    line = next(li for li in response.json()["estimate"]["line_items"] if li["item_id"] == "CMT01")
    assert line["unit_price"] == 300
    assert audit.call_args.kwargs["corrections"]["unit_prices"] == {"CMT01":300}
    assert audit.call_args.kwargs["corrections"]["reason"] == "Supplier quotation"


@pytest.mark.parametrize("price", [-1, True, "300", None])
def test_api_refuses_invalid_price_values(original, price):
    response = TestClient(app).post("/api/estimate/recalculate", json={
        "original_input":original.model_dump(mode="json"), "corrections":{"unit_prices":{"CMT01":price}},
    })
    assert response.status_code == 422


def test_api_refuses_overflow_in_total(original):
    response = TestClient(app).post("/api/estimate/recalculate", json={
        "original_input":original.model_dump(mode="json"), "corrections":{"unit_prices":{"CMT01":1e308}},
    })
    assert response.status_code == 422
