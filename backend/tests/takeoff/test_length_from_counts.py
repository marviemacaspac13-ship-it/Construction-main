"""Length derived from counts, when nothing measured it.

Wire, conduit and pipe are sold by the metre and are the majority of both
trades - about 65% of electrical. No drawing states those lengths and
nothing in the app measures them, so `plan.runs` has been empty on every
estimate ever produced and the rules that price it never fired. Electrical
came to P1,224 against a realistic P18,000-25,000.

These allowances turn the counts we can read into the lengths we cannot.
They are the most expensive guesses in the engine, so what is pinned here
is not their accuracy - nothing could pin that - but that they are applied
consistently, flagged honestly, and always yield to a real measurement.
"""

import pytest

from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.electrical import compute as electrical_compute
from app.takeoff.rules.plumbing import compute as plumbing_compute
from app.takeoff.schema import FixtureCount, PlanSchema, Run

DEFAULTS = EstimatingParams()

DEVICES = PlanSchema(
    plan_type="Electrical Plan",
    source="detection",
    fixtures=[FixtureCount(item_id="OT01", count=8), FixtureCount(item_id="CLR01", count=13)],
)
FIXTURES = PlanSchema(
    plan_type="Plumbing Plan",
    source="tags",
    fixture_tags={"water_closet": 8, "lavatory": 12, "floor_drain": 13, "cleanout": 3},
)


def rules_in(lines) -> set[str]:
    return {li.rule for li in lines}


def metres(lines, rule: str, item_id: str | None = None) -> float:
    """Devices behind a rule, times nothing - the raw input, before waste."""
    return sum(
        li.inputs.get("devices", li.inputs.get("route_length_m", 0))
        for li in lines
        if li.rule == rule and (item_id is None or li.item_id == item_id)
    )


# --- the allowances exist and are bounded -------------------------------

def test_the_allowances_have_defaults():
    assert DEFAULTS.wire_m_per_device == 12.0
    assert DEFAULTS.conduit_m_per_device == 6.0
    assert DEFAULTS.main_run_m_per_fixture == 1.5


def test_an_allowance_cannot_be_negative():
    with pytest.raises(ValueError):
        EstimatingParams(wire_m_per_device=-1)


# --- a measurement always wins ------------------------------------------

def test_a_measured_route_suppresses_the_derived_one():
    """The single most important behaviour here.

    If both applied, an estimate would pay for its wire twice - once
    measured and once guessed - and the guess would be invisible inside
    the total.
    """
    measured = DEVICES.model_copy(
        update={
            "runs": [
                Run(id="c1", length_m=40.0, service="lighting", conductors=2, terminations=6)
            ]
        }
    )
    lines = electrical_compute(measured, DEFAULTS)
    assert "electrical.conductor" in rules_in(lines)
    assert "electrical.conductor_from_count" not in rules_in(lines)
    assert "electrical.conduit_from_count" not in rules_in(lines)


def test_without_a_route_the_derived_rule_fires():
    lines = electrical_compute(DEVICES, DEFAULTS)
    assert "electrical.conductor_from_count" in rules_in(lines)
    assert "electrical.conductor" not in rules_in(lines)


def test_the_two_rules_are_named_differently_on_purpose():
    """The ledger records rule names; a reader must tell measured from guessed."""
    derived = rules_in(electrical_compute(DEVICES, DEFAULTS))
    assert not {"electrical.conductor", "electrical.conduit"} & derived


# --- electrical ---------------------------------------------------------

def test_gauge_follows_what_the_device_is_for():
    """Lighting circuits take #14, convenience #12 - the measured split."""
    lines = [li for li in electrical_compute(DEVICES, DEFAULTS)
             if li.rule == "electrical.conductor_from_count"]
    by_item = {li.item_id: li for li in lines}
    assert set(by_item) == {"ELW05", "ELW04"}
    # 13 ceiling outlets at 12 m + 10% waste
    assert by_item["ELW05"].quantity == pytest.approx(13 * 12.0 * 1.10)
    # 8 wall outlets at 12 m + 10% waste
    assert by_item["ELW04"].quantity == pytest.approx(8 * 12.0 * 1.10)


def test_conduit_covers_every_device_regardless_of_gauge():
    lines = [li for li in electrical_compute(DEVICES, DEFAULTS)
             if li.rule == "electrical.conduit_from_count"]
    assert len(lines) == 1
    assert lines[0].item_id == "FPVC01"
    assert lines[0].quantity == pytest.approx(21 * 6.0 * 1.10)


def test_no_devices_means_no_wire_rather_than_a_zero_line():
    empty = PlanSchema(plan_type="Electrical Plan", source="detection")
    assert electrical_compute(empty, DEFAULTS) == []


def test_a_zero_allowance_disables_the_line_cleanly():
    off = EstimatingParams(wire_m_per_device=0, conduit_m_per_device=0)
    rules = rules_in(electrical_compute(DEVICES, off))
    assert "electrical.conductor_from_count" not in rules
    assert "electrical.conduit_from_count" not in rules


def test_the_derivation_says_it_was_not_measured():
    """An ELW04 line otherwise reads as though someone traced the circuits."""
    lines = electrical_compute(DEVICES, DEFAULTS)
    assert all(
        "DERIVED from the count" in li.derivation
        for li in lines
        if li.rule.endswith("_from_count")
    )


# --- plumbing -----------------------------------------------------------

def test_the_main_run_scales_with_the_fixture_count():
    lines = [li for li in plumbing_compute(FIXTURES, DEFAULTS) if li.rule == "plumbing.main_run"]
    # 33 fixtures that imply materials; cleanouts do not.
    assert all(li.inputs["route_length_m"] == pytest.approx(33 * 1.5) for li in lines)


def test_a_cleanout_pulls_no_main_run():
    only_cleanouts = PlanSchema(
        plan_type="Plumbing Plan", source="tags", fixture_tags={"cleanout": 5}
    )
    assert "plumbing.main_run" not in rules_in(plumbing_compute(only_cleanouts, DEFAULTS))


def test_a_water_closet_puts_the_main_at_four_inches():
    lines = [li for li in plumbing_compute(FIXTURES, DEFAULTS) if li.rule == "plumbing.main_run"]
    assert "PDP03" in {li.item_id for li in lines}


def test_without_a_water_closet_two_inches_carries_it():
    no_wc = PlanSchema(
        plan_type="Plumbing Plan", source="tags", fixture_tags={"lavatory": 4}
    )
    lines = [li for li in plumbing_compute(no_wc, DEFAULTS) if li.rule == "plumbing.main_run"]
    assert {li.item_id for li in lines} == {"PDP01", "PCSP01"}


def test_a_zero_main_run_disables_it():
    off = EstimatingParams(main_run_m_per_fixture=0)
    assert "plumbing.main_run" not in rules_in(plumbing_compute(FIXTURES, off))


# --- the point of the whole exercise ------------------------------------

def test_electrical_reaches_a_believable_order_of_magnitude(catalog):
    """P1,224 was under a tenth of a real bungalow electrical estimate."""
    total = estimate_plan(DEVICES, catalog).grand_total
    assert 8_000 < total < 30_000


def test_wire_is_now_the_largest_line(catalog):
    """It is roughly two thirds of the trade, and it was absent entirely."""
    result = estimate_plan(DEVICES, catalog)
    biggest = max(result.line_items, key=lambda li: li.line_total)
    assert biggest.item_id.startswith("ELW")


def test_plumbing_rises_once_the_main_run_is_counted(catalog):
    with_main = estimate_plan(FIXTURES, catalog).grand_total
    off = EstimatingParams(main_run_m_per_fixture=0)
    without = estimate_plan(FIXTURES, catalog, off).grand_total
    assert with_main > without


def test_nothing_derived_goes_unpriced(catalog):
    assert estimate_plan(DEVICES, catalog).unpriced == []
    assert estimate_plan(FIXTURES, catalog).unpriced == []


# --- flagged, and reaching the ledger -----------------------------------

def test_the_electrical_allowance_is_declared():
    line = [a for a in DEFAULTS.assumption_lines({"electrical"})
            if "derived from the device count" in a]
    assert len(line) == 1
    assert "largest single cost" in line[0]


def test_the_plumbing_main_run_is_declared():
    assert any(
        "shared run back to the main" in a
        for a in DEFAULTS.assumption_lines({"plumbing"})
    )


def test_an_electrical_estimate_carries_its_own_assumption_and_not_the_other_trades(catalog):
    assumptions = estimate_plan(DEVICES, catalog).assumptions
    assert any("derived from the device count" in a for a in assumptions)
    assert not any("shared run back to the main" in a for a in assumptions)
