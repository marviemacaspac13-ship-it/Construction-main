"""Which concrete gets reinforced, and how the steel is bought.

The *quantities* are the project guide and live in test_guide_bills.py -
duplicating them here would mean two places to update and two chances to
disagree. What is left for this file is the plumbing around them: elements
that cannot be reinforced, kinds with no rule, tie wire, and the fact that
several rules buying the same bar must come out as one purchase.
"""

import pytest

from app.extract.to_plan import extract_plan, to_plan_schema
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.structural import beam_stirrup_count, compute
from app.takeoff.schema import ConcreteElement, PlanSchema
from tests.fixtures.sample_plans import KERALA

DEFAULTS = EstimatingParams()

COLUMNS = ConcreteElement(
    id="columns", kind="column", volume_m3=3.29, count=15,
    width_m=0.20, length_m=0.40, height_m=2.7432,
)
FOOTINGS = ConcreteElement(
    id="footings", kind="footing", volume_m3=3.97, count=15,
    width_m=1.15, length_m=1.15, height_m=0.20,
)
BEAM = ConcreteElement(
    id="beam", kind="beam", volume_m3=4.0, count=1,
    width_m=0.20, length_m=50.0, height_m=0.40,
)
SLAB = ConcreteElement(
    id="slab", kind="slab", volume_m3=15.4, count=1,
    width_m=14.0, length_m=11.0, height_m=0.10,
)


def plan_with(*elements: ConcreteElement) -> PlanSchema:
    return PlanSchema(plan_type="Floor Plan", concrete=list(elements))


def kerala_schema() -> PlanSchema:
    return to_plan_schema(
        extract_plan(
            KERALA.envelope_w, KERALA.envelope_l, KERALA.room_blocks,
            KERALA.chains, KERALA.opening_tags,
        )
    )


def rules_in(plan: PlanSchema) -> set[str]:
    return {li.rule for li in compute(plan, DEFAULTS)}


# --- every kind the frame produces now has a rule ----------------------

@pytest.mark.parametrize(
    "element,expected",
    [
        (COLUMNS, {"structural.column_bars", "structural.column_ties"}),
        (FOOTINGS, {"structural.footing_bars"}),
        (BEAM, {"structural.beam_bars", "structural.beam_stirrups"}),
        (SLAB, {"structural.slab_mesh"}),
    ],
    ids=["column", "footing", "beam", "slab"],
)
def test_each_element_kind_is_reinforced(element, expected):
    assert expected <= rules_in(plan_with(element))


def test_beams_are_reinforced_now():
    """They were poured bare until the guide specified them."""
    assert "structural.beam_stirrups" in rules_in(plan_with(BEAM))


# --- what is deliberately left bare ------------------------------------

def test_a_volume_without_geometry_is_poured_but_not_reinforced():
    """A hand-entered pour has no members to reinforce; guessing would be worse."""
    bare = ConcreteElement(id="misc", kind="column", volume_m3=2.0)
    assert not bare.is_reinforceable
    rules = rules_in(plan_with(bare))
    assert "structural.concrete" in rules
    assert not any(r.startswith("structural.column_") for r in rules)


def test_a_member_too_small_for_its_cover_gets_no_ties():
    """Not a real section, but it must not produce negative steel."""
    tiny = COLUMNS.model_copy(update={"width_m": 0.05, "length_m": 0.05})
    assert "structural.column_ties" not in rules_in(plan_with(tiny))


def test_a_footing_too_small_for_its_cover_gets_no_bars():
    tiny = FOOTINGS.model_copy(update={"width_m": 0.10, "length_m": 0.10})
    assert "structural.footing_bars" not in rules_in(plan_with(tiny))


def test_a_zero_length_beam_gets_no_stirrups():
    assert beam_stirrup_count(0) == 0


# --- how the steel is bought -------------------------------------------

def test_rules_sharing_a_bar_become_one_purchase(catalog):
    """Column ties, beam stirrups, slab mesh and CHB wall bars are all DB01.

    Four lines for one SKU would be an unbuyable estimate.
    """
    result = estimate_plan(kerala_schema(), catalog)
    db01 = [li for li in result.line_items if li.item_id == "DB01"]
    assert len(db01) == 1
    for rule in ("structural.slab_mesh", "structural.column_ties", "structural.rebar"):
        assert rule in db01[0].rule


def test_the_guide_main_bar_is_bought_as_one_line(catalog):
    """Column verticals, beam mains and footing mats are all DB03."""
    result = estimate_plan(kerala_schema(), catalog)
    db03 = [li for li in result.line_items if li.item_id == "DB03"]
    assert len(db03) == 1
    for rule in ("structural.column_bars", "structural.footing_bars", "structural.beam_bars"):
        assert rule in db03[0].rule


def test_bars_are_bought_in_whole_lengths(catalog):
    result = estimate_plan(kerala_schema(), catalog)
    for li in result.line_items:
        if li.item_id in {"DB01", "DB02", "DB03"}:
            assert li.quantity == int(li.quantity)


def test_frame_steel_brings_its_own_tie_wire():
    lines = compute(plan_with(COLUMNS, FOOTINGS, BEAM, SLAB), DEFAULTS)
    assert any(li.rule == "structural.tie_wire" for li in lines)


def test_everything_the_frame_produces_is_priceable(catalog):
    assert estimate_plan(kerala_schema(), catalog).unpriced == []


def test_frame_steel_is_a_material_share_of_the_total(catalog):
    """A flagged assumption that changed nothing would be cosmetic."""
    schema = kerala_schema()
    full = estimate_plan(schema, catalog).grand_total
    stripped = schema.model_copy(
        update={"concrete": [e.model_copy(update={"width_m": None}) for e in schema.concrete]}
    )
    bare = estimate_plan(stripped, catalog).grand_total
    assert full > bare
    assert 0.10 < (full - bare) / full < 0.40


# --- stated as assumed --------------------------------------------------

def test_lap_splices_are_declared_uncounted():
    """The one thing genuinely not computed - say so rather than imply it."""
    assert any("Lap splices are not counted" in a for a in DEFAULTS.assumption_lines())


def test_no_frame_means_no_frame_claims():
    off = EstimatingParams(include_frame=False)
    assert not any("Lap splices" in a for a in off.assumption_lines())
