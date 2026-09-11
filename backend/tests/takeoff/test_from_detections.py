"""The detections -> PlanSchema adapter.

This is what lets Electrical and Plumbing plans be estimated at all: the
OCR reader cannot handle them, but symbol matching can count their devices
and fittings, and the same rule engine prices the result.
"""

import pytest

from app.schemas import Detection
from app.takeoff.estimator import estimate_plan
from app.takeoff.from_detections import plan_from_detections, unknown_labels


def det(label, confidence=0.9):
    return Detection(label=label, confidence=confidence, bbox=[0, 0, 10, 10])


def test_detections_become_fixture_counts():
    plan = plan_from_detections([det("OT01"), det("OT01"), det("SW01")], "Electrical Plan")
    assert {f.item_id: f.count for f in plan.fixtures} == {"OT01": 2, "SW01": 1}
    assert plan.source == "detection"


def test_fixtures_come_out_in_a_stable_order():
    """Two runs over the same detections must produce the same record."""
    detections = [det("SW01"), det("OT01"), det("CLR01")]
    a = [f.item_id for f in plan_from_detections(detections, "Electrical Plan").fixtures]
    b = [f.item_id for f in plan_from_detections(detections, "Electrical Plan").fixtures]
    assert a == b == ["CLR01", "OT01", "SW01"]


def test_geometry_stays_empty_because_it_cannot_be_detected():
    plan = plan_from_detections([det("OT01")], "Electrical Plan")
    assert plan.runs == []
    assert plan.walls == []
    assert plan.rooms == []


def test_plan_type_is_carried_through():
    assert plan_from_detections([], "Plumbing Plan").plan_type == "Plumbing Plan"


def test_unknown_labels_are_dropped_not_crashed():
    plan = plan_from_detections([det("mystery_symbol"), det("OT01")], "Electrical Plan")
    assert {f.item_id for f in plan.fixtures} == {"OT01"}


def test_unknown_labels_are_reportable():
    """Dropped is not the same as hidden - an operator must be able to see them."""
    detections = [det("mystery_symbol"), det("OT01"), det("another_unknown")]
    assert unknown_labels(detections) == ["another_unknown", "mystery_symbol"]


def test_no_detections_gives_an_empty_plan():
    plan = plan_from_detections([], "Electrical Plan")
    assert plan.fixtures == []


# --- the whole point: these plan types can now be priced -----------------

def test_electrical_detections_price_end_to_end(catalog):
    detections = (
        [det("OT01")] * 8
        + [det("SW01")] * 5
        + [det("CLR01")] * 6
        + [det("CBR02")] * 4
        + [det("PB01")]
    )
    result = estimate_plan(plan_from_detections(detections, "Electrical Plan"), catalog)

    assert result.unpriced == []
    assert result.grand_total > 0
    by_sku = {li.item_id: li.quantity for li in result.line_items}
    assert by_sku["OT01"] == 8
    assert by_sku["SW01"] == 5
    assert by_sku["CLR01"] == 6
    # Boxes are derived by the rules, not detected.
    assert by_sku["UTB01"] == 13  # 8 outlets + 5 switches
    assert by_sku["JCB01"] == 6   # one per ceiling outlet


def test_plumbing_detections_price_end_to_end(catalog):
    detections = [det("PVTB01")] * 6 + [det("PVYO01")] * 3
    result = estimate_plan(plan_from_detections(detections, "Plumbing Plan"), catalog)

    assert result.unpriced == []
    by_sku = {li.item_id: li.quantity for li in result.line_items}
    assert by_sku["PVTB01"] == 6
    assert by_sku["PVYO01"] == 3
    # Pipe needs run lengths, which detection cannot supply.
    assert not any(k.startswith("PCSP") or k.startswith("PDP") for k in by_sku)


def test_a_floor_plan_of_detections_prices_nothing_useful(catalog):
    """Detection cannot supply wall geometry, so masonry stays absent.

    This is why the OCR path exists, and why the two are complementary.
    """
    result = estimate_plan(plan_from_detections([det("OT01")], "Floor Plan"), catalog)
    assert result.line_items == []