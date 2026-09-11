"""Plumbing Plan rules.

Like the electrical module, this had never been executed. Pipe is sold in
fixed 3 m lengths, so the interesting behaviour is metres -> sticks.
"""

import pytest

from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.plumbing import compute
from app.takeoff.schema import FixtureCount, PlanSchema, Run


def by_item(lines):
    out: dict[str, float] = {}
    for line in lines:
        out[line.item_id] = out.get(line.item_id, 0.0) + line.quantity
    return out


@pytest.mark.parametrize(
    "diameter,expected",
    [('1/2"', "PCSP01"), ('3/4"', "PCSP02")],
)
def test_supply_diameter_selects_the_sku(diameter, expected):
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        runs=[Run(id="r1", length_m=12.0, service="supply", diameter=diameter)],
    )
    assert expected in by_item(compute(plan, EstimatingParams()))


@pytest.mark.parametrize(
    "diameter,expected",
    [('2"', "PDP01"), ('3"', "PDP02"), ('4"', "PDP03")],
)
def test_drain_diameter_selects_the_sku(diameter, expected):
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        runs=[Run(id="r1", length_m=9.0, service="drain", diameter=diameter)],
    )
    assert expected in by_item(compute(plan, EstimatingParams()))


def test_pipe_quantity_is_in_sticks_not_metres():
    # 12 m + 5% waste = 12.6 m, / 3 m per stick = 4.2 sticks
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        runs=[Run(id="r1", length_m=12.0, service="supply", diameter='1/2"')],
    )
    assert by_item(compute(plan, EstimatingParams()))["PCSP01"] == pytest.approx(4.2)


def test_two_runs_of_the_same_diameter_accumulate():
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        runs=[
            Run(id="r1", length_m=12.0, service="supply", diameter='1/2"'),
            Run(id="r2", length_m=6.0, service="supply", diameter='1/2"'),
        ],
    )
    # (12 + 6) x 1.05 / 3 = 6.3 sticks
    assert by_item(compute(plan, EstimatingParams()))["PCSP01"] == pytest.approx(6.3)


def test_supply_and_drain_of_the_same_size_do_not_collide():
    """A 2 inch drain is a different SKU from any supply pipe."""
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        runs=[
            Run(id="s1", length_m=9.0, service="supply", diameter='1/2"'),
            Run(id="d1", length_m=9.0, service="drain", diameter='2"'),
        ],
    )
    items = by_item(compute(plan, EstimatingParams()))
    assert set(items) == {"PCSP01", "PDP01"}


def test_fittings_pass_through_as_counts():
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        fixtures=[
            FixtureCount(item_id="PVTO01", count=9),
            FixtureCount(item_id="PVYB02", count=2),
        ],
    )
    items = by_item(compute(plan, EstimatingParams()))
    assert items["PVTO01"] == 9
    assert items["PVYB02"] == 2


def test_unknown_diameter_is_rejected_loudly():
    """An unmapped size must not be silently dropped from the estimate."""
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        runs=[Run(id="r1", length_m=5.0, service="supply", diameter='6"')],
    )
    with pytest.raises(KeyError):
        compute(plan, EstimatingParams())


def test_electrical_runs_are_ignored_here():
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        runs=[Run(id="r1", length_m=5.0, service="lighting")],
    )
    assert compute(plan, EstimatingParams()) == []


def test_a_plumbing_run_without_a_diameter_is_rejected_at_the_schema():
    with pytest.raises(ValueError):
        Run(id="r1", length_m=5.0, service="supply")


def test_empty_plan_produces_nothing():
    assert compute(PlanSchema(plan_type="Plumbing Plan"), EstimatingParams()) == []


def test_plumbing_plan_prices_end_to_end(catalog):
    plan = PlanSchema(
        plan_type="Plumbing Plan",
        fixtures=[
            FixtureCount(item_id="PVTB01", count=6),
            FixtureCount(item_id="PVYO01", count=3),
        ],
        runs=[
            Run(id="s1", length_m=18.0, service="supply", diameter='1/2"'),
            Run(id="d1", length_m=12.0, service="drain", diameter='4"'),
        ],
    )
    result = estimate_plan(plan, catalog)
    assert result.unpriced == []
    by_sku = {li.item_id: li for li in result.line_items}
    # 18 m + 5% = 18.9 / 3 = 6.3 sticks -> 7
    assert by_sku["PCSP01"].quantity == 7
    # 12 m + 5% = 12.6 / 3 = 4.2 sticks -> 5
    assert by_sku["PDP03"].quantity == 5
    assert by_sku["PVTB01"].quantity == 6