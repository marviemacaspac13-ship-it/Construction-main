"""The structural frame is assumed, so the tests pin the assumptions.

There is no ground truth to check against here - no sample plan states its
column schedule. What can be checked is that the derivation is internally
consistent, that the knobs actually move the concrete, and that an assumed
frame never passes itself off as a measured one.
"""

import json
from pathlib import Path

import pytest

from app.extract.to_plan import extract_plan, to_plan_schema
from app.takeoff.estimator import estimate_plan
from app.takeoff.frame import column_count, derive_frame
from app.takeoff.params import EstimatingParams
from tests.fixtures.sample_plans import ALL_PLANS, CAD_WIDE, KERALA

DEFAULTS = EstimatingParams()
NO_FRAME = EstimatingParams(include_frame=False)


def plan_of(sample, params=None):
    return extract_plan(
        sample.envelope_w, sample.envelope_l, sample.room_blocks,
        sample.chains, sample.opening_tags, params,
    )


# --- column layout ------------------------------------------------------

def test_columns_sit_on_the_perimeter_at_the_given_spacing():
    # 14 x 11 -> 50 m of perimeter, 50 / 3.5 = 14.3 -> 15 posts round the loop.
    assert column_count(14.0, 11.0, 3.5) == 15


def test_a_closed_loop_does_not_get_a_fencepost_extra():
    """A 40 m perimeter at 4 m spacing closes on 10 columns, not 11."""
    assert column_count(12.0, 8.0, 4.0) == 10


def test_even_a_tiny_building_gets_its_four_corners():
    assert column_count(2.0, 2.0, 3.5) == 4


def test_no_envelope_means_no_columns():
    assert column_count(0.0, 0.0, 3.5) == 0


# --- volumes ------------------------------------------------------------

def test_volumes_follow_the_stated_sections():
    frame = derive_frame(14.0, 11.0, DEFAULTS)
    assert frame.column_count == 15
    # 15 columns x 0.20 x 0.20 x 3.0 m wall height
    assert frame.column_volume_m3 == pytest.approx(1.80)
    # 15 footings x 0.80 x 0.80 x 0.20
    assert frame.footing_volume_m3 == pytest.approx(1.92)
    # 14 x 11 x 0.10 slab on grade
    assert frame.slab_volume_m3 == pytest.approx(15.40)
    assert frame.total_volume_m3 == pytest.approx(19.12)


def test_concrete_scales_with_the_square_of_the_column_section():
    """The reason the section is worth flagging: 0.30 is 2.25x the 0.20."""
    thin = derive_frame(14.0, 11.0, DEFAULTS)
    thick = derive_frame(
        14.0, 11.0, EstimatingParams(column_width_m=0.30, column_depth_m=0.30)
    )
    assert thick.column_volume_m3 == pytest.approx(thin.column_volume_m3 * 2.25)


def test_elements_carry_their_mix_class():
    frame = derive_frame(14.0, 11.0, DEFAULTS)
    by_kind = {e.kind: e for e in frame.elements}
    assert set(by_kind) == {"footing", "column", "slab"}
    # Footings and columns carry load; a slab on grade does not.
    assert by_kind["footing"].mix_class == "A"
    assert by_kind["column"].mix_class == "A"
    assert by_kind["slab"].mix_class == "B"


def test_element_volumes_sum_to_the_derivation():
    frame = derive_frame(14.0, 11.0, DEFAULTS)
    assert sum(e.volume_m3 for e in frame.elements) == pytest.approx(
        frame.total_volume_m3
    )


def test_a_zero_slab_drops_the_element_rather_than_pouring_nothing():
    frame = derive_frame(14.0, 11.0, EstimatingParams(slab_thickness_m=0))
    assert frame.slab_volume_m3 == 0
    assert {e.kind for e in frame.elements} == {"footing", "column"}


# --- switched off / absent ---------------------------------------------

def test_no_frame_is_distinguishable_from_an_empty_one():
    """None means nothing was derived; it must not read as zero concrete."""
    assert derive_frame(14.0, 11.0, NO_FRAME) is None
    assert derive_frame(0.0, 11.0, DEFAULTS) is None


# --- through the extraction --------------------------------------------

@pytest.mark.parametrize("sample", ALL_PLANS, ids=[p.key for p in ALL_PLANS])
def test_every_sample_plan_derives_a_frame(sample):
    frame = plan_of(sample).frame
    assert frame is not None
    assert frame.column_count >= 4
    assert frame.total_volume_m3 > 0


def test_the_frame_reaches_the_plan_schema():
    schema = to_plan_schema(plan_of(CAD_WIDE))
    assert {e.kind for e in schema.concrete} == {"footing", "column", "slab"}


def test_an_assumed_frame_says_so():
    warnings = plan_of(CAD_WIDE).warnings()
    assert any("Concrete is assumed, not read" in w for w in warnings)


def test_switching_the_frame_off_removes_both_concrete_and_its_warning():
    extraction = plan_of(CAD_WIDE, NO_FRAME)
    assert to_plan_schema(extraction).concrete == []
    assert not any("Concrete is assumed" in w for w in extraction.warnings())


def test_the_sections_used_are_stated_on_every_estimate():
    line = [
        a for a in DEFAULTS.assumption_lines() if "Structural frame assumed" in a
    ]
    assert len(line) == 1
    assert "0.2 x 0.2 m columns at 3.5 m o.c." in line[0]
    assert "0.1 m slab on grade" in line[0]


def test_no_frame_states_no_frame_assumption():
    assert not any(
        "Structural frame" in a for a in NO_FRAME.assumption_lines()
    )


# --- pricing ------------------------------------------------------------

def test_the_frame_is_priced_and_every_line_matches_a_sku(catalog):
    result = estimate_plan(to_plan_schema(plan_of(KERALA)), catalog)
    assert result.unpriced == []
    # Gravel appears only through concrete - walls do not use it.
    assert "GVF01" in {li.item_id for li in result.line_items}


def test_the_frame_costs_real_money(catalog):
    """A flagged assumption that changed nothing would be cosmetic."""
    with_frame = estimate_plan(to_plan_schema(plan_of(KERALA)), catalog)
    without = estimate_plan(to_plan_schema(plan_of(KERALA, NO_FRAME)), catalog)
    assert with_frame.grand_total > without.grand_total * 1.5


def test_mortar_cement_and_frame_cement_stay_one_purchase(catalog):
    """Both rules buy CMT01; the estimate must not list it twice."""
    result = estimate_plan(to_plan_schema(plan_of(KERALA)), catalog)
    cement = [li for li in result.line_items if li.item_id == "CMT01"]
    assert len(cement) == 1
    assert "laying mortar" in cement[0].derivation
    assert "Class A concrete" in cement[0].derivation
