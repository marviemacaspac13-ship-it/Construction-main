"""The extraction logic, exercised against all four real sample plans."""

import pytest

from app.extract.chains import drop_cumulative, validate_chain
from app.extract.to_plan import extract_plan, to_plan_schema
from app.extract.tokens import classify_tag, count_openings, parse_room
from app.extract.units_infer import infer_units
from app.takeoff.estimator import estimate_plan
from tests.fixtures.sample_plans import ALL_PLANS, CAD_WIDE, KERALA, NOTEBOOK


def ids(plans):
    return [p.key for p in plans]


# --- token parsing -------------------------------------------------------

@pytest.mark.parametrize(
    "text,name,w,l",
    [
        ("KITCHEN 3700 x 4000", "KITCHEN", 3700, 4000),
        ("BED ROOM 294X294", "BED ROOM", 294, 294),
        ("LIVING ROOM\n5400 x 3800", "LIVING ROOM", 5400, 3800),
        ("SIT-OUT 312X138", "SIT-OUT", 312, 138),
        ("W/C 192X138", "W/C", 192, 138),
        ("BATHROOM 2 3000 x 1500", "BATHROOM 2", 3000, 1500),
    ],
)
def test_room_strings_parse(text, name, w, l):
    room = parse_room(text)
    assert room is not None
    assert room.name == name
    assert (room.width, room.length) == (w, l)


def test_text_without_dimensions_is_not_a_room():
    assert parse_room("STAIRCASE") is None
    assert parse_room("UP") is None


def test_opening_tags_classify():
    assert classify_tag("W3") == "window"
    assert classify_tag("D1") == "door"
    assert classify_tag("D") == "door"
    assert classify_tag("V") is None  # ventilator, not an opening we deduct


def test_kerala_opening_counts():
    counts = count_openings(KERALA.opening_tags)
    assert counts == {"door": 6, "window": 9}


# --- unit inference ------------------------------------------------------

@pytest.mark.parametrize("plan", ALL_PLANS, ids=ids(ALL_PLANS))
def test_units_are_inferred_correctly(plan):
    inference = infer_units(max(plan.envelope_w, plan.envelope_l))
    assert inference.unit == plan.expected_unit
    assert inference.confidence > 0.9


@pytest.mark.parametrize("plan", ALL_PLANS, ids=ids(ALL_PLANS))
def test_envelope_lands_in_a_believable_range(plan):
    inference = infer_units(max(plan.envelope_w, plan.envelope_l))
    metres = inference.to_metres(max(plan.envelope_w, plan.envelope_l))
    assert 3.0 <= metres <= 60.0


def test_absurd_magnitude_is_flagged_not_accepted():
    assert infer_units(500000).confidence < 0.5


# --- chain checksums -----------------------------------------------------

@pytest.mark.parametrize("plan", ALL_PLANS, ids=ids(ALL_PLANS))
def test_every_chain_on_every_plan_closes(plan):
    for values, stated in plan.chains:
        check = validate_chain(values, stated)
        assert check.ok, (
            f"{plan.key}: {values} sums to {check.total} not {stated}"
        )


def test_cumulative_running_total_is_dropped():
    # Kerala's left chain carries 954, the running sum of the seven before it.
    values = [96, 150, 140, 50, 200, 150, 168, 954, 95]
    kept, dropped = drop_cumulative(values)
    assert dropped == [954]
    assert sum(kept) == 1049


def test_chain_tolerates_hand_dimension_rounding():
    # 318+360+215+132 = 1025 against a stated 1026.
    check = validate_chain([318, 360, 215, 132], 1026)
    assert check.ok
    assert check.error == -1


def test_a_misread_digit_breaks_the_checksum():
    # 3200 misread as 8200 must NOT pass silently.
    check = validate_chain([8200, 3700, 3300, 3800], 14000)
    assert not check.ok
    assert check.error == 5000


# --- end to end ----------------------------------------------------------

@pytest.mark.parametrize("plan", ALL_PLANS, ids=ids(ALL_PLANS))
def test_extraction_is_high_confidence_with_no_warnings_about_chains(plan):
    ex = extract_plan(
        plan.envelope_w, plan.envelope_l, plan.room_blocks, plan.chains, plan.opening_tags
    )
    # Three closing chains score lower than four - fewer independent
    # witnesses - so the bar is per-chain agreement, not a fixed number.
    assert all(c.ok for c in ex.chain_checks), ex.warnings()
    assert ex.confidence > 0.80, ex.warnings()
    assert not any("does not close" in w for w in ex.warnings())


@pytest.mark.parametrize("plan", ALL_PLANS, ids=ids(ALL_PLANS))
def test_wall_derivation_is_physically_plausible(plan):
    ex = extract_plan(plan.envelope_w, plan.envelope_l, plan.room_blocks, plan.chains)
    walls = ex.walls
    # Total wall must exceed the exterior alone and stay under a silly bound.
    assert walls.total_m > walls.exterior_m
    assert walls.total_m < 400
    # Rooms must account for a meaningful share of the envelope.
    assert ex.area.accounted_ratio > 0.55


@pytest.mark.parametrize("plan", ALL_PLANS, ids=ids(ALL_PLANS))
def test_each_plan_prices_to_a_sane_estimate(plan, catalog):
    ex = extract_plan(
        plan.envelope_w, plan.envelope_l, plan.room_blocks, plan.chains, plan.opening_tags
    )
    result = estimate_plan(to_plan_schema(ex), catalog)

    assert result.unpriced == []
    assert result.grand_total > 0
    priced = {li.item_id for li in result.line_items}
    # A floor plan must produce blocks, mortar and reinforcement.
    assert {"CHB01", "CHB02", "CMT01", "SND02", "DB01", "GI01"} <= priced
    # Discrete SKUs must come out whole.
    for li in result.line_items:
        if li.item_id in {"CHB01", "CHB02", "CMT01", "DB01"}:
            assert li.quantity == int(li.quantity)


def test_notebook_wall_length_matches_hand_calculation():
    # Room perimeters sum to 103.6 m; envelope perimeter 43.6 m.
    # (103.6 + 43.6) / 2 = 73.6 m
    ex = extract_plan(
        NOTEBOOK.envelope_w, NOTEBOOK.envelope_l, NOTEBOOK.room_blocks, NOTEBOOK.chains
    )
    assert ex.walls.room_perimeter_sum_m == pytest.approx(103.6)
    assert ex.walls.exterior_m == pytest.approx(43.6)
    assert ex.walls.total_m == pytest.approx(73.6)


def test_cad_wide_wall_length_matches_hand_calculation():
    # Room perimeters 133.8 m, envelope perimeter 50 m -> 91.9 m
    ex = extract_plan(
        CAD_WIDE.envelope_w, CAD_WIDE.envelope_l, CAD_WIDE.room_blocks, CAD_WIDE.chains
    )
    assert ex.walls.room_perimeter_sum_m == pytest.approx(133.8)
    assert ex.walls.exterior_m == pytest.approx(50.0)
    assert ex.walls.total_m == pytest.approx(91.9)


def test_openings_reduce_the_block_count():
    with_tags = extract_plan(
        KERALA.envelope_w, KERALA.envelope_l, KERALA.room_blocks, KERALA.chains,
        KERALA.opening_tags,
    )
    without = extract_plan(
        KERALA.envelope_w, KERALA.envelope_l, KERALA.room_blocks, KERALA.chains, []
    )
    a = sum(w.opening_area_m2 for w in to_plan_schema(with_tags).walls)
    b = sum(w.opening_area_m2 for w in to_plan_schema(without).walls)
    assert a > b > -1