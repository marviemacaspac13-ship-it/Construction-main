"""Reinforcement inside the frame: column bars and ties, footing mats, slab mesh.

Assumed like the sections they sit in - a plan that does not state its
column schedule does not state its bar schedule either - so these tests pin
the arithmetic rather than any ground truth. The numbers are worked by hand
in each docstring, so a changed rule shows up as a changed expectation
rather than a quietly different price.
"""

import pytest

from app.extract.to_plan import extract_plan, to_plan_schema
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.structural import compute
from app.takeoff.schema import ConcreteElement, PlanSchema
from tests.fixtures.sample_plans import KERALA

DEFAULTS = EstimatingParams()


def plan_with(*elements: ConcreteElement) -> PlanSchema:
    return PlanSchema(plan_type="Floor Plan", concrete=list(elements))


def length_for(plan: PlanSchema, rule: str, params: EstimatingParams = DEFAULTS) -> float:
    """Bar metres a rule produced, before waste."""
    lines = [li for li in compute(plan, params) if li.rule == rule]
    return sum(li.inputs["rebar_length_m"] for li in lines)


def items_for(plan: PlanSchema, rule: str) -> set[str]:
    return {li.item_id for li in compute(plan, DEFAULTS) if li.rule == rule}


def kerala_schema() -> PlanSchema:
    return to_plan_schema(
        extract_plan(
            KERALA.envelope_w, KERALA.envelope_l, KERALA.room_blocks,
            KERALA.chains, KERALA.opening_tags,
        )
    )


COLUMNS = ConcreteElement(
    id="columns", kind="column", volume_m3=0.48, count=4,
    width_m=0.20, length_m=0.20, height_m=3.0,
)
FOOTINGS = ConcreteElement(
    id="footings", kind="footing", volume_m3=0.512, count=4,
    width_m=0.80, length_m=0.80, height_m=0.20,
)
SLAB = ConcreteElement(
    id="slab", kind="slab", volume_m3=10.0, count=1,
    width_m=10.0, length_m=10.0, height_m=0.10,
)


# --- columns ------------------------------------------------------------

def test_column_verticals_are_bars_times_height_times_count():
    """4 columns x 4 bars x 3.0 m = 48 m."""
    assert length_for(plan_with(COLUMNS), "structural.column_bars") == pytest.approx(48.0)


def test_column_verticals_use_the_heavier_bar():
    assert items_for(plan_with(COLUMNS), "structural.column_bars") == {"DB02"}


def test_ties_are_closed_loops_inside_the_cover():
    """0.20 less 2 x 0.04 cover = 0.12 square, so a 0.48 m loop.

    3.0 m at 0.20 m o.c. is 15 gaps and therefore 16 ties.
    4 columns x 16 ties x 0.48 m = 30.72 m.
    """
    assert length_for(plan_with(COLUMNS), "structural.column_ties") == pytest.approx(30.72)


def test_a_column_too_small_for_its_cover_gets_no_ties():
    """Not a real section, but it must not produce negative steel."""
    tiny = COLUMNS.model_copy(update={"width_m": 0.05, "length_m": 0.05})
    assert length_for(plan_with(tiny), "structural.column_ties") == 0


def test_dropping_the_verticals_leaves_the_ties():
    bare = EstimatingParams(column_bars=0)
    plan = plan_with(COLUMNS)
    assert length_for(plan, "structural.column_bars", bare) == 0
    assert length_for(plan, "structural.column_ties", bare) > 0


# --- footings -----------------------------------------------------------

def test_footing_mats_span_the_clear_dimension_both_ways():
    """0.80 less 2 x 0.075 cover = 0.65 clear. 0.65 at 0.20 o.c. is 5 bars.

    5 x 0.65 each way = 6.5 m per footing, x 4 = 26.0 m.
    """
    assert length_for(plan_with(FOOTINGS), "structural.footing_bars") == pytest.approx(26.0)


def test_footings_take_the_largest_cover():
    """Cast against earth, so they lose more length to cover than a slab does."""
    as_slab = FOOTINGS.model_copy(update={"kind": "slab", "count": 4})
    footing = length_for(plan_with(FOOTINGS), "structural.footing_bars")
    slab = length_for(plan_with(as_slab), "structural.slab_mesh")
    assert slab > footing


# --- slab ---------------------------------------------------------------

def test_slab_mesh_covers_the_whole_pour():
    """9.96 m clear at 0.25 o.c. is 41 bars; 41 x 9.96 each way = 816.72 m."""
    assert length_for(plan_with(SLAB), "structural.slab_mesh") == pytest.approx(816.72)


def test_a_wider_mesh_spacing_buys_less_steel():
    plan = plan_with(SLAB)
    tight = length_for(plan, "structural.slab_mesh", EstimatingParams(slab_mesh_spacing_m=0.20))
    loose = length_for(plan, "structural.slab_mesh", EstimatingParams(slab_mesh_spacing_m=0.40))
    assert tight > loose > 0


# --- what does not get reinforced --------------------------------------

def test_a_volume_without_geometry_is_poured_but_not_reinforced():
    """A hand-entered pour has no members to reinforce; guessing would be worse."""
    bare = ConcreteElement(id="misc", kind="column", volume_m3=2.0)
    assert not bare.is_reinforceable
    lines = compute(plan_with(bare), DEFAULTS)
    assert any(li.rule == "structural.concrete" for li in lines)
    assert not any(li.rule.startswith("structural.column_") for li in lines)


def test_beams_have_no_reinforcement_rule_yet():
    beam = ConcreteElement(
        id="beams", kind="beam", volume_m3=1.0, count=4,
        width_m=0.20, length_m=0.40, height_m=3.0,
    )
    lines = compute(plan_with(beam), DEFAULTS)
    assert any(li.rule == "structural.concrete" for li in lines)
    assert not any("bars" in li.rule or "mesh" in li.rule for li in lines)


# --- tie wire and merging ----------------------------------------------

def test_frame_steel_brings_its_own_tie_wire():
    lines = compute(plan_with(COLUMNS, FOOTINGS, SLAB), DEFAULTS)
    assert sum(1 for li in lines if li.rule == "structural.tie_wire") > 0


def test_slab_mesh_and_wall_bars_are_one_purchase(catalog):
    """Both are DB01. Two lines for one SKU would be an unbuyable estimate."""
    result = estimate_plan(kerala_schema(), catalog)
    db01 = [li for li in result.line_items if li.item_id == "DB01"]
    assert len(db01) == 1
    assert "structural.rebar" in db01[0].rule
    assert "structural.slab_mesh" in db01[0].rule


def test_bars_are_bought_in_whole_lengths(catalog):
    result = estimate_plan(kerala_schema(), catalog)
    for li in result.line_items:
        if li.item_id in {"DB01", "DB02", "DB03"}:
            assert li.quantity == int(li.quantity)


def test_frame_steel_is_a_material_share_of_the_total(catalog):
    """It was worth building: bare concrete under-stated by roughly a fifth."""
    schema = kerala_schema()
    full = estimate_plan(schema, catalog).grand_total

    stripped = schema.model_copy(
        update={"concrete": [e.model_copy(update={"width_m": None}) for e in schema.concrete]}
    )
    bare = estimate_plan(stripped, catalog).grand_total
    assert full > bare
    assert 0.10 < (full - bare) / full < 0.30


# --- stated as assumed --------------------------------------------------

def test_the_bar_schedule_used_is_stated_on_every_estimate():
    line = [a for a in DEFAULTS.assumption_lines() if "Frame steel assumed" in a]
    assert len(line) == 1
    assert "4 x DB02 per column" in line[0]
    # Laps are the one thing genuinely not counted - say so rather than imply it.
    assert "Lap splices are not counted" in line[0]


def test_no_frame_means_no_frame_steel_claim():
    off = EstimatingParams(include_frame=False)
    assert not any("Frame steel" in a for a in off.assumption_lines())
