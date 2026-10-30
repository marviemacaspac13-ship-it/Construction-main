"""Corrections must rebuild dependent purchases without changing the source scan."""
import math
from unittest.mock import patch
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.takeoff.bom import merge_bom
from app.takeoff.constants import SLAB_MESH_M_PER_M2
from app.takeoff.contracts import (
    ElectricalDeviceId, EstimateCorrections, EstimateInputSnapshot, snapshot_catalog,
)
from app.takeoff.corrections import IncompatibleSnapshot, recalculate
from app.takeoff.estimator import estimate_plan
from app.takeoff.frame import derive_frame
from app.takeoff.params import EstimatingParams
from app.takeoff.rules import structural
from app.takeoff.schema import FixtureCount, PlanSchema, Run, Wall
from app.takeoff.units import DISCRETE_KINDS, UNIT_SPECS


@pytest.fixture
def original(catalog):
    params = EstimatingParams()
    return EstimateInputSnapshot(
        plan=PlanSchema(plan_type="Floor Plan", source="ocr",
                        walls=[Wall(id="wall", length_m=15, height_m=2.7)],
                        concrete=derive_frame(10, 12, params, drawn_columns=14).elements),
        params=params, prices=snapshot_catalog(catalog, "2026-10-11T00:00:00Z"),
    )


def correct(original, **quantities):
    return recalculate(original, EstimateCorrections(quantities=quantities))


def members(plan):
    return {el.kind: el for el in plan.concrete}


def test_slab_uses_one_area_for_concrete_mesh_and_tie_wire(original):
    before = members(original.plan)
    result = correct(original, slab_area_m2=73.25)
    after = members(result.effective_input.plan)
    assert after["slab"].volume_m3 == pytest.approx(7.325)
    assert after["slab"].width_m == before["slab"].width_m
    assert after["slab"].length_m == before["slab"].length_m
    for kind in ("beam", "column", "footing"):
        assert before[kind] == after[kind]
    mesh = structural._slab_steel(after["slab"], original.params)
    assert mesh[0].quantity == pytest.approx(73.25 * SLAB_MESH_M_PER_M2 * 1.05 / 6)
    assert mesh[1].quantity > 0
    assert result.effective_input.plan.walls == original.plan.walls


@pytest.mark.parametrize("count", [0, 1, 2, 100])
def test_manual_columns_ignore_plausibility_and_rebuild_linked_footings(original, count):
    result = correct(original, column_count=count)
    before, after = members(original.plan), members(result.effective_input.plan)
    assert after["beam"] == before["beam"]
    assert after["slab"] == before["slab"]
    for kind in ("column", "footing"):
        if count == 0:
            assert kind not in after
        else:
            el = after[kind]
            assert el.count == count
            assert el.volume_m3 == pytest.approx(count * el.width_m * el.length_m * el.height_m)
            assert not el.counted
    assert any(f"Columns manually confirmed: {count}" in s for s in result.estimate.assumptions)
    assert not any("Columns were counted" in s or "columns at" in s for s in result.estimate.assumptions)


def test_zero_excludes_slab_but_null_keeps_original(original):
    assert "slab" not in members(correct(original, slab_area_m2=0).effective_input.plan)
    assert correct(original, slab_area_m2=None).effective_input == original


def test_global_height_replaces_explicit_heights_without_changing_frame(original):
    result = correct(original, wall_height_m=3.2)
    assert result.effective_input.plan.walls[0].height_m == 3.2
    assert result.effective_input.params.default_wall_height_m == 3.2
    assert result.effective_input.plan.concrete == original.plan.concrete
    before = {li.item_id: li.quantity for li in correct(original).estimate.line_items}
    after = {li.item_id: li.quantity for li in result.estimate.line_items}
    assert after["CHB02"] > before["CHB02"]
    assert after["DB01"] > before["DB01"]


def test_repeated_edits_reset_and_snapshot_replay(original):
    saved = original.model_dump_json()
    first = correct(original, slab_area_m2=60, column_count=2, wall_height_m=3.2)
    second = correct(original, slab_area_m2=60, column_count=2, wall_height_m=3.2)
    assert first.effective_input == second.effective_input
    assert first.estimate.line_items == second.estimate.line_items
    assert original.model_dump_json() == saved
    replay = estimate_plan(first.effective_input.plan, original.prices.to_catalog(), first.effective_input.params)
    assert replay.model_dump(exclude={"priced_at"}) == first.estimate.model_dump(exclude={"priced_at"})
    assert correct(original).effective_input == original
    assert first.effective_input.prices == original.prices


def test_merge_then_round_with_nondefault_waste_and_unpriced_lines(original):
    original.params.rebar_waste = 0.13
    result = correct(original, slab_area_m2=17.123, column_count=3)
    plan, params = result.effective_input.plan, result.effective_input.params
    raw = structural.compute(plan, params)
    merged = {line.item_id: line for line in merge_bom(raw)}
    assert len([li for li in raw if li.item_id == "DB01"]) > 1
    assert len([li for li in raw if li.item_id == "GI01"]) > 1
    for line in result.estimate.line_items:
        quantity = merged[line.item_id].quantity
        expected = (math.ceil(round(quantity, 6)) if UNIT_SPECS[line.item_id].kind in DISCRETE_KINDS
                    else round(quantity, 2))
        assert line.quantity == expected
        assert line.line_total == round(expected * line.unit_price, 2)
    assert result.estimate.grand_total == round(sum(li.line_total for li in result.estimate.line_items), 2)
    catalog = original.prices.to_catalog()
    del catalog["DB01"]
    original.prices = snapshot_catalog(catalog, "2026-10-11T00:00:00Z")
    assert any(li.item_id == "DB01" for li in correct(original, slab_area_m2=17.123).estimate.unpriced)


def test_electrical_replaces_duplicate_groups_and_recomputes_dependencies(original):
    original.plan = PlanSchema(plan_type="Electrical Plan", source="detection", fixtures=[
        FixtureCount(item_id="OT01", count=2), FixtureCount(item_id="OT01", count=3),
        FixtureCount(item_id="CLR01", count=4)])
    result = correct(original, electrical_counts={"OT01": 1, "OT02": 2})
    assert {f.item_id: f.count for f in result.effective_input.plan.fixtures} == {"OT01": 1, "OT02": 2, "CLR01": 4}
    direct = original.plan.model_copy(deep=True)
    direct.fixtures = [FixtureCount(item_id=k, count=v) for k,v in {"OT01":1, "OT02":2, "CLR01":4}.items()]
    assert result.estimate.line_items == estimate_plan(direct, original.prices.to_catalog(), original.params).line_items
    zero = correct(original, electrical_counts={"OT01":0, "CLR01":0})
    assert zero.estimate.line_items == []
    assert zero.estimate.grand_total == 0


def test_electrical_measured_routes_are_preserved(original):
    original.plan = PlanSchema(plan_type="Electrical Plan", runs=[Run(id="r", length_m=12, service="convenience")])
    result = correct(original, electrical_counts={"OT01":5})
    assert result.effective_input.plan.runs == original.plan.runs
    assert not any("from_count" in li.rule for li in result.estimate.line_items)


def test_plumbing_reprices_branches_main_and_preserves_counted_only_cleanouts(original):
    original.plan = PlanSchema(plan_type="Plumbing Plan", source="tags", fixture_tags={"water_closet":4, "lavatory":2})
    result = correct(original, plumbing_counts={"water_closet":1, "floor_drain":2, "cleanout":3})
    assert result.effective_input.plan.fixture_tags == {"water_closet":1, "lavatory":2, "floor_drain":2, "cleanout":3}
    lines = {li.item_id: li for li in result.estimate.line_items}
    # One WC branch plus shared drain for five served fixtures, merged before
    # whole-stick rounding. Cleanouts do not add a sixth/seventh/eighth branch.
    assert lines["PDP03"].quantity == math.ceil((2 + 5 * 1.5) * 1.05 / 3)
    assert "plumbing.fixture_drain" in lines["PDP03"].rule
    assert "plumbing.main_run" in lines["PDP03"].rule
    assert not any(li.item_id == "cleanout" for li in result.estimate.line_items)
    zero = correct(original, plumbing_counts={"water_closet":0, "lavatory":0})
    assert zero.estimate.grand_total == 0


@pytest.mark.parametrize("field,value", [("column_count",-1), ("column_count",True), ("column_count",1.2),
    ("slab_area_m2",float("inf")), ("slab_area_m2",float("nan")), ("wall_height_m",0),
    ("slab_area_m2",True), ("wall_height_m","3.2"),
    ("electrical_counts",{"PB01":1}), ("plumbing_counts",{"bidet":1}),
    ("electrical_counts",{"OT01":None})])
def test_invalid_corrections_rejected(original, field, value):
    with pytest.raises(ValidationError):
        correct(original, **{field:value})


@pytest.mark.parametrize("quantities", [{"electrical_counts":{"OT01":0}}, {"plumbing_counts":{"lavatory":0}}])
def test_wrong_trade_rejected_even_for_zero(original, quantities):
    with pytest.raises(ValueError):
        correct(original, **quantities)


@pytest.mark.parametrize("kind,quantity", [("column",{"column_count":2}), ("footing",{"column_count":2}),
                                         ("slab",{"slab_area_m2":60})])
def test_missing_or_ambiguous_geometry_is_rejected(original, kind, quantity):
    original.plan.concrete = [el for el in original.plan.concrete if el.kind != kind]
    with pytest.raises(ValueError, match="original needs"):
        correct(original, **quantity)


def test_version_and_unit_mismatch_rejected(original):
    original.rules_version = "obsolete"
    with pytest.raises(IncompatibleSnapshot):
        correct(original)


def test_purchase_unit_mismatch_rejected(original):
    from app.takeoff.contracts import _catalog_hash
    row = next(row for row in original.prices.items if row.item_id == "DB01")
    row.purchase_unit = row.purchase_unit.model_copy(update={"stick_length_m":5})
    original.prices.snapshot_id = _catalog_hash(original.prices.items)
    with pytest.raises(IncompatibleSnapshot, match="purchase units"):
        correct(original)


def test_ambiguous_members_and_mismatched_footings_rejected(original):
    original.plan.concrete.append(members(original.plan)["slab"].model_copy(deep=True))
    with pytest.raises(ValueError, match="original needs"):
        correct(original, slab_area_m2=60)
    members(original.plan)["footing"].count += 1
    with pytest.raises(ValueError, match="different counts"):
        correct(original, column_count=5)


def test_missing_wall_geometry_rejected(original):
    original.plan.walls = []
    with pytest.raises(ValueError, match="wall lengths"):
        correct(original, wall_height_m=3)


@pytest.mark.parametrize("item_id", get_args(ElectricalDeviceId))
def test_existing_device_semantics_supported_without_new_classification(original, item_id):
    original.plan = PlanSchema(plan_type="Electrical Plan")
    result = correct(original, electrical_counts={item_id:3})
    assert next(li for li in result.estimate.line_items if li.item_id == item_id).quantity == 3


def test_explicit_slab_area_rejects_stale_volume(original):
    data = members(original.plan)["slab"].model_dump()
    data["slab_area_m2"] = 50
    with pytest.raises(ValidationError, match="slab volume"):
        type(members(original.plan)["slab"]).model_validate(data)


@pytest.mark.ocr
def test_real_floor_scan_corrects_and_resets_without_rereading(catalog):
    from app.main import _read_plan
    raw = (Path(__file__).parents[1] / "fixtures" / "plans" / "01.png").read_bytes()
    plan, _ = _read_plan(raw, "Floor Plan")
    original = EstimateInputSnapshot(plan=plan, params=EstimatingParams(),
                                    prices=snapshot_catalog(catalog, "2026-10-11T00:00:00Z"))
    before = original.model_dump_json()
    with patch("app.main._read_plan", side_effect=AssertionError("must not reread")):
        result = correct(original, wall_height_m=3.2, slab_area_m2=80, column_count=2)
        reset = correct(original)
    assert original.model_dump_json() == before
    assert members(result.effective_input.plan)["column"].count == 2
    assert members(result.effective_input.plan)["slab"].volume_m3 == pytest.approx(8)
    assert result.effective_input.plan.walls != original.plan.walls
    assert reset.effective_input == original
    assert reset.estimate.line_items == estimate_plan(plan, catalog, original.params).line_items


def test_nested_nonfinite_input_rejected(original):
    original.plan.walls[0].length_m = float("inf")
    with pytest.raises(ValueError):
        correct(original)


def test_api_computes_without_catalog_ocr_or_writes_and_audits(original):
    payload = {"original_input":original.model_dump(mode="json"), "corrections":{"quantities":{"column_count":2}}}
    with patch("app.materials._client", side_effect=AssertionError("no database")), \
         patch("app.corrections.audit.record_estimate") as audit:
        response = TestClient(app).post("/api/estimate/recalculate", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["effective_input"]["plan"]["manual_column_count"] == 2
    assert audit.call_args.kwargs["corrections"]["quantities"]["column_count"] == 2
    payload["corrections"]["quantities"] = {"electrical_counts":{"OT01":1}}
    assert TestClient(app).post("/api/estimate/recalculate", json=payload).status_code == 422
    payload["original_input"]["rules_version"] = "obsolete"
    assert TestClient(app).post("/api/estimate/recalculate", json=payload).status_code == 409
