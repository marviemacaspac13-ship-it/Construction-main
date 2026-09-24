"""The project guide reproduced, member by member.

`Guide.docx` works out a bill of materials for four standard members and
highlights the totals, saying those totals are the base of the calculation.
This file is those totals. If a constant or a formula drifts, one of these
fails and names which member moved.

Quantities are checked on the BOM rather than the priced estimate, because
the estimate rounds discrete SKUs up to whole purchases and the guide does
not. The one exception is CHB, where the guide itself rounds to 178.
"""

import pytest

from app.takeoff.constants import (
    COLUMN_SECTION_M,
    COLUMN_STANDARD_HEIGHT_M,
    FOOTING_SIDE_M,
)
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.structural import beam_stirrup_count, compute
from app.takeoff.schema import ConcreteElement, PlanSchema, Wall

PARAMS = EstimatingParams()


def bom(plan: PlanSchema):
    return compute(plan, PARAMS)


def quantity(lines, item_id: str, rule: str | None = None) -> float:
    """Total quantity of one SKU, optionally from one rule only."""
    return sum(
        li.quantity for li in lines if li.item_id == item_id and (rule is None or li.rule == rule)
    )


def bar_metres(lines, rule: str) -> float:
    """Bar length before waste, which is what the guide quotes."""
    return sum(li.inputs["rebar_length_m"] for li in lines if li.rule == rule)


def only(*elements: ConcreteElement) -> PlanSchema:
    return PlanSchema(plan_type="Floor Plan", concrete=list(elements))


# --- the guide standard column: 0.20 x 0.40 x 2.7432 --------------------

COLUMN = ConcreteElement(
    id="c", kind="column",
    volume_m3=COLUMN_SECTION_M[0] * COLUMN_SECTION_M[1] * COLUMN_STANDARD_HEIGHT_M,
    count=1,
    width_m=COLUMN_SECTION_M[0],
    length_m=COLUMN_SECTION_M[1],
    height_m=COLUMN_STANDARD_HEIGHT_M,
)


def test_the_column_section_is_the_guide_section():
    assert COLUMN_SECTION_M == (0.20, 0.40)
    assert COLUMN_STANDARD_HEIGHT_M == 2.7432
    assert COLUMN.volume_m3 == pytest.approx(0.21946, abs=1e-5)


def test_column_vertical_bars():
    """Guide: 4 16mm x 2.7432 m = 10.9728 m of 16mm."""
    assert bar_metres(bom(only(COLUMN)), "structural.column_bars") == pytest.approx(10.9728)


def test_column_ties():
    """Guide: 24 pcs x 0.88 m = 21.12 m of 10mm.

    The 0.88 loop is 2 x ((200 - 80) + (400 - 80)) mm at 40 mm cover.
    """
    assert bar_metres(bom(only(COLUMN)), "structural.column_ties") == pytest.approx(21.12)


def test_column_concrete():
    """Guide: 1.83 bags cement, 0.101 m3 sand, 0.203 m3 gravel, incl. 5% waste.

    Cement lands on 1.82500 here against the guide 1.83. Same number: the
    guide carries 69.52 / 40 = 1.738 bags through as "1.7", and
    1.738 x 1.05 = 1.825, which it then prints rounded up.
    """
    lines = bom(only(COLUMN))
    assert quantity(lines, "CMT01") == pytest.approx(1.825, abs=0.001)
    assert quantity(lines, "SND02") == pytest.approx(0.101, abs=0.0005)
    assert quantity(lines, "GVF01") == pytest.approx(0.203, abs=0.0005)


# --- the guide standard beam: 0.20 x 0.40, worked at 5 m ----------------

BEAM = ConcreteElement(
    id="b", kind="beam", volume_m3=0.20 * 0.40 * 5.0, count=1,
    width_m=0.20, length_m=5.0, height_m=0.40,
)


def test_beam_stirrup_schedule():
    """Guide: 11 + 6 + 8 + 16 = 41 stirrups on a 5 m beam."""
    assert beam_stirrup_count(5.0) == 41


def test_a_beam_shorter_than_the_zones_gets_only_what_fits():
    """The zones total 2.0 m; a 0.4 m beam cannot carry all of them."""
    assert 0 < beam_stirrup_count(0.4) < 41


def test_beam_main_bars():
    """Guide: 16mm = 4 x Length, so 20 m on a 5 m beam."""
    assert bar_metres(bom(only(BEAM)), "structural.beam_bars") == pytest.approx(20.0)


def test_beam_stirrup_steel():
    """Guide: 36.08 m of 10mm, which is 41 x 0.88."""
    assert bar_metres(bom(only(BEAM)), "structural.beam_stirrups") == pytest.approx(36.08)


def test_beam_concrete():
    """Guide: 3.3264 bags, 0.1848 m3 sand, 0.3696 m3 gravel on a 5 m beam."""
    lines = bom(only(BEAM))
    assert quantity(lines, "CMT01") == pytest.approx(3.3264, abs=0.001)
    assert quantity(lines, "SND02") == pytest.approx(0.1848, abs=0.0005)
    assert quantity(lines, "GVF01") == pytest.approx(0.3696, abs=0.0005)


# --- the guide standard slab: 5 x 5, 100 mm ----------------------------

SLAB = ConcreteElement(
    id="s", kind="slab", volume_m3=25 * 0.10, count=1,
    width_m=5.0, length_m=5.0, height_m=0.10,
)


def test_slab_mesh():
    """Guide: 210 m of 10mm over 25 m2, which is 8.4 m/m2 after 5% waste."""
    lines = bom(only(SLAB))
    metres = bar_metres(lines, "structural.slab_mesh")
    assert metres == pytest.approx(200.0)
    assert metres * 1.05 == pytest.approx(210.0)


def test_slab_sand_and_gravel():
    """Guide: 1.16 m3 sand and 2.31 m3 gravel over 25 m2."""
    lines = bom(only(SLAB))
    assert quantity(lines, "SND02") == pytest.approx(1.16, abs=0.006)
    assert quantity(lines, "GVF01") == pytest.approx(2.31, abs=0.005)


def test_slab_cement_departs_from_the_guide_on_purpose():
    """The guide slab line omits the waste its own sand and gravel carry.

    2.5 m3 x 7.92 = 19.80 bags is the guide figure, but 1.16 and 2.31 are
    both post-waste on the same line. Waste is applied uniformly here, so
    cement comes out at 20.79 rather than 19.80. Pinned so the departure is
    deliberate and visible rather than a drift nobody noticed.
    """
    assert quantity(bom(only(SLAB)), "CMT01") == pytest.approx(20.79, abs=0.01)


# --- the guide standard footing ----------------------------------------

FOOTING = ConcreteElement(
    id="f", kind="footing", volume_m3=FOOTING_SIDE_M**2 * 0.20, count=1,
    width_m=FOOTING_SIDE_M, length_m=FOOTING_SIDE_M, height_m=0.20,
)


def test_footing_bars():
    """Guide: cut length 1.15 - 2(0.075) = 1.00 m, 6 + 6 bars = 12.0 m of 16mm."""
    assert bar_metres(bom(only(FOOTING)), "structural.footing_bars") == pytest.approx(12.0)


def test_footing_bars_are_16mm_not_10mm():
    lines = [li for li in bom(only(FOOTING)) if li.rule == "structural.footing_bars"]
    assert {li.item_id for li in lines} == {"DB03"}


# --- the guide standard wall: 5.00 x 2.70, 6 inch ----------------------

WALL_PLAN = PlanSchema(
    plan_type="Floor Plan",
    walls=[Wall(id="w", length_m=5.0, thickness="6in", height_m=2.7)],
)


def test_wall_blocks(catalog):
    """Guide: 13.50 / 0.08 = 168.75, +5% = 177.19, bought as 178 pcs."""
    raw = quantity(bom(WALL_PLAN), "CHB02")
    assert raw == pytest.approx(177.1875)
    priced = estimate_plan(WALL_PLAN, catalog)
    assert next(li.quantity for li in priced.line_items if li.item_id == "CHB02") == 178


def test_the_default_wall_height_is_the_guide_wall():
    """A floor plan never states wall height, so the default IS the estimate.

    It was an unsourced 3.0 m until Sep 2026 while this bill said 2.70, and
    every floor-plan estimate carried the difference - about 2.6%. Tying the
    default to the bill means changing one without the other fails here.
    """
    guide_wall = WALL_PLAN.walls[0]
    assert EstimatingParams().default_wall_height_m == guide_wall.height_m == 2.7


def test_wall_mortar():
    """Guide: 2.86 bags of cement and 0.11 m3 of sand for the same wall."""
    lines = bom(WALL_PLAN)
    assert quantity(lines, "CMT01") == pytest.approx(2.86, abs=0.005)
    assert quantity(lines, "SND02") == pytest.approx(0.11, abs=0.0005)


def test_a_four_inch_wall_takes_less_mortar_than_a_six_inch_one():
    """The guide gives one wall example and does not separate the two."""
    four = PlanSchema(
        plan_type="Floor Plan",
        walls=[Wall(id="w", length_m=5.0, thickness="4in", height_m=2.7)],
    )
    assert quantity(bom(four), "CMT01") < quantity(bom(WALL_PLAN), "CMT01")
