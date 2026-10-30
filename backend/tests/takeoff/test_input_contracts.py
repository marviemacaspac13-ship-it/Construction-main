"""Snapshots must reproduce costs and reject ambiguous correction inputs."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.takeoff.contracts import (
    EstimateCorrections, EstimateInputSnapshot, PriceSnapshot,
    SourceQuantityOverrides, snapshot_catalog,
)
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import PlanSchema, Wall

AT = "2026-10-10T01:00:00Z"


def test_snapshot_reproduces_estimate_after_live_prices_change(catalog):
    plan = PlanSchema(plan_type="Floor Plan", walls=[Wall(id="w1", length_m=10)])
    params = EstimatingParams(default_wall_height_m=2.8, chb_waste=0.07)
    original = estimate_plan(plan, catalog, params)
    snapshot = EstimateInputSnapshot(
        plan=plan, params=params, prices=snapshot_catalog(catalog, AT),
    )
    saved = EstimateInputSnapshot.model_validate_json(snapshot.model_dump_json())
    changed = deepcopy(catalog)
    changed["CHB02"]["price"] *= 2
    assert estimate_plan(plan, changed, params).grand_total != original.grand_total
    replay = estimate_plan(saved.plan, saved.prices.to_catalog(), saved.params)
    assert replay.line_items == original.line_items
    assert replay.unpriced == original.unpriced
    assert replay.grand_total == original.grand_total
    assert saved.params.default_wall_height_m == 2.8
    assert len(saved.prices.items) == len(catalog)


def test_catalog_hash_is_order_independent_but_detects_content_changes(catalog):
    original = snapshot_catalog(catalog, AT)
    reordered = snapshot_catalog(dict(reversed(list(catalog.items()))), "2026-10-11T01:00:00Z")
    assert reordered.snapshot_id == original.snapshot_id
    changed = deepcopy(catalog)
    changed["CHB02"]["price"] += 1
    assert snapshot_catalog(changed, AT).snapshot_id != original.snapshot_id
    data = original.model_dump(mode="json")
    data["items"][0]["price"] += 1
    with pytest.raises(ValidationError, match="content does not match"):
        PriceSnapshot.model_validate(data)


def test_snapshot_keeps_display_and_purchase_units_separate(catalog):
    snapshot = snapshot_catalog(catalog, AT)
    pipe = next(item for item in snapshot.items if item.item_id == "PCSP01")
    assert pipe.unit == catalog["PCSP01"]["unit"]
    assert pipe.purchase_unit.kind == "stick"
    assert pipe.purchase_unit.stick_length_m == 3


def test_zero_corrections_are_not_replaced_by_defaults():
    correction = EstimateCorrections(
        quantities={"column_count": 0, "slab_area_m2": 0,
                    "electrical_counts": {"OT01": 0},
                    "plumbing_counts": {"water_closet": 0}},
        unit_prices={"OT01": 0},
    )
    restored = EstimateCorrections.model_validate_json(correction.model_dump_json())
    assert restored.quantities.column_count == 0
    assert restored.quantities.slab_area_m2 == 0
    assert restored.quantities.electrical_counts == {"OT01": 0}
    assert restored.quantities.plumbing_counts == {"water_closet": 0}
    assert restored.unit_prices == {"OT01": 0}
    assert restored.quantities.wall_height_m is None


@pytest.mark.parametrize("payload", [
    {"column_count": -1}, {"column_count": 1.5}, {"column_count": True},
    {"column_count": "2"}, {"slab_area_m2": float("nan")},
    {"slab_area_m2": float("inf")}, {"wall_height_m": 0},
    {"wall_height_m": 11}, {"electrical_counts": {"NOT_A_SKU": 1}},
    {"electrical_counts": {"OT01": 0.5}},
    {"plumbing_counts": {"bidet": 1}},
    {"plumbing_counts": {"water_closet": -1}}, {"wall_heigth_m": 3},
])
def test_invalid_source_corrections_are_rejected(payload):
    with pytest.raises(ValidationError):
        SourceQuantityOverrides.model_validate(payload)


@pytest.mark.parametrize("prices", [
    {"NOT_A_SKU": 10}, {"OT01": -1}, {"OT01": float("inf")},
])
def test_invalid_price_corrections_are_rejected(prices):
    with pytest.raises(ValidationError):
        EstimateCorrections(unit_prices=prices)


def test_unknown_input_schema_version_is_rejected(catalog):
    with pytest.raises(ValidationError):
        EstimateInputSnapshot(
            schema_version=2, plan=PlanSchema(plan_type="Floor Plan"),
            params=EstimatingParams(), prices=snapshot_catalog(catalog, AT),
        )
