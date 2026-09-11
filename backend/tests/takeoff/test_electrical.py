"""Electrical Plan rules.

This module had never been executed before these tests existed. Expected
values below are computed by hand from the constants, not read back out of
the implementation.
"""

import pytest

from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.electrical import compute
from app.takeoff.schema import FixtureCount, PlanSchema, Run


def by_item(lines):
    """Sum quantities per SKU - a rule may emit several lines for one SKU."""
    out: dict[str, float] = {}
    for line in lines:
        out[line.item_id] = out.get(line.item_id, 0.0) + line.quantity
    return out


# --- devices -------------------------------------------------------------

def test_fixtures_pass_through_as_counts():
    plan = PlanSchema(
        plan_type="Electrical Plan", fixtures=[FixtureCount(item_id="OT02", count=7)]
    )
    assert by_item(compute(plan, EstimatingParams()))["OT02"] == 7


def test_zero_count_fixtures_are_dropped():
    plan = PlanSchema(
        plan_type="Electrical Plan", fixtures=[FixtureCount(item_id="OT02", count=0)]
    )
    assert compute(plan, EstimatingParams()) == []


def test_one_utility_box_per_wiring_device():
    plan = PlanSchema(
        plan_type="Electrical Plan",
        fixtures=[
            FixtureCount(item_id="OT01", count=4),
            FixtureCount(item_id="GS02", count=3),
            FixtureCount(item_id="CBR01", count=5),  # panel gear, not a wiring device
            FixtureCount(item_id="PB01", count=1),   # nor is the panel board
        ],
    )
    assert by_item(compute(plan, EstimatingParams()))["UTB01"] == 7


def test_one_junction_box_per_ceiling_outlet():
    plan = PlanSchema(
        plan_type="Electrical Plan",
        fixtures=[
            FixtureCount(item_id="CLR01", count=4),
            FixtureCount(item_id="CLR03", count=2),
        ],
    )
    assert by_item(compute(plan, EstimatingParams()))["JCB01"] == 6


def test_ceiling_outlets_do_not_also_get_utility_boxes():
    plan = PlanSchema(
        plan_type="Electrical Plan", fixtures=[FixtureCount(item_id="CLR01", count=5)]
    )
    items = by_item(compute(plan, EstimatingParams()))
    assert items["JCB01"] == 5
    assert "UTB01" not in items


# --- conductors and conduit ---------------------------------------------

@pytest.mark.parametrize(
    "service,expected",
    [
        ("lighting", "ELW05"),          # #14 AWG
        ("convenience", "ELW04"),       # #12 AWG
        ("aircon", "ELW03"),            # #10 AWG
        ("service_entrance", "ELW01"),  # #6 AWG
    ],
)
def test_wire_gauge_is_chosen_by_service(service, expected):
    plan = PlanSchema(
        plan_type="Electrical Plan",
        runs=[Run(id="r1", length_m=10.0, service=service)],
    )
    items = by_item(compute(plan, EstimatingParams()))
    assert expected in items
    assert len([k for k in items if k.startswith("ELW")]) == 1


def test_wire_length_covers_conductors_slack_and_waste():
    # (10 m route + 3 terminations x 0.30 m) x 2 conductors x 1.10 waste
    plan = PlanSchema(
        plan_type="Electrical Plan",
        runs=[Run(id="r1", length_m=10.0, service="convenience", conductors=2, terminations=3)],
    )
    assert by_item(compute(plan, EstimatingParams()))["ELW04"] == pytest.approx(23.98)


def test_conduit_follows_route_length_not_conductor_count():
    """Three conductors share one conduit - the pipe does not triple."""
    plan = PlanSchema(
        plan_type="Electrical Plan",
        runs=[Run(id="r1", length_m=10.0, service="lighting", conductors=3)],
    )
    assert by_item(compute(plan, EstimatingParams()))["FPVC01"] == pytest.approx(11.0)


def test_two_runs_of_the_same_service_are_both_counted():
    plan = PlanSchema(
        plan_type="Electrical Plan",
        runs=[
            Run(id="r1", length_m=10.0, service="lighting"),
            Run(id="r2", length_m=5.0, service="lighting"),
        ],
    )
    items = by_item(compute(plan, EstimatingParams()))
    assert items["ELW05"] == pytest.approx(33.0)   # (10+5) x 2 x 1.10
    assert items["FPVC01"] == pytest.approx(16.5)  # (10+5) x 1.10


def test_plumbing_runs_are_ignored_here():
    plan = PlanSchema(
        plan_type="Electrical Plan",
        runs=[Run(id="r1", length_m=10.0, service="supply", diameter='1/2"')],
    )
    assert compute(plan, EstimatingParams()) == []


def test_empty_plan_produces_nothing():
    assert compute(PlanSchema(plan_type="Electrical Plan"), EstimatingParams()) == []


# --- end to end ----------------------------------------------------------

def test_electrical_plan_prices_end_to_end(catalog):
    """A realistic small house circuit, priced through the real catalog."""
    plan = PlanSchema(
        plan_type="Electrical Plan",
        fixtures=[
            FixtureCount(item_id="OT01", count=8),
            FixtureCount(item_id="SW01", count=5),
            FixtureCount(item_id="CLR01", count=6),
            FixtureCount(item_id="PB01", count=1),
            FixtureCount(item_id="CBR02", count=4),
        ],
        runs=[
            Run(id="c1", length_m=32.0, service="lighting", conductors=2, terminations=11),
            Run(id="c2", length_m=25.0, service="convenience", conductors=3, terminations=8),
        ],
    )
    result = estimate_plan(plan, catalog)

    assert result.unpriced == []
    assert result.grand_total > 0
    priced = {li.item_id for li in result.line_items}
    assert {"OT01", "SW01", "CLR01", "PB01", "CBR02", "UTB01", "JCB01",
            "ELW05", "ELW04", "FPVC01"} <= priced
    # Device counts are whole; wire is metres and may carry decimals.
    for li in result.line_items:
        if li.item_id in {"OT01", "SW01", "UTB01", "JCB01"}:
            assert li.quantity == int(li.quantity)
    # PB01 has a null unit in the catalog - that must not break pricing.
    assert next(li for li in result.line_items if li.item_id == "PB01").unit is None