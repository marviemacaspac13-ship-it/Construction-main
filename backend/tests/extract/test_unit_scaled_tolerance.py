"""Chain tolerances are real distances, not bare numbers.

The checksum is the whole basis for trusting a number with nobody in the
loop. It had a flat absolute floor of 2.0, which is 2 mm on a millimetre
drawing - correctly nothing - and two METRES on a plan dimensioned in
metres, where it validated almost any misread and pushed confidence up
while doing it. Worse than absent: confidently wrong.

These tests fix the tolerance to a physical length at every scale, and
guard the four millimetre and centimetre plans against moving at all.
"""

import pytest

from app.extract.chains import (
    ABS_TOL_M,
    MM_PER_UNIT,
    drop_cumulative,
    tolerance_in_units,
    validate_chain,
)
from app.extract.reader import _match_chain
from app.extract.tokens import MAX_ROOM_ASPECT, is_plausible_room, parse_rooms
from app.extract.to_plan import extract_plan
from app.extract.units_infer import infer_units
from tests.fixtures.sample_plans import ALL_PLANS

MM, CM, M = 0.001, 0.01, 1.0


# --- the conversion itself ---------------------------------------------

@pytest.mark.parametrize(
    "metres_per_unit,expected",
    [(MM, 2.0), (CM, 0.2), (M, 0.002)],
    ids=["mm", "cm", "m"],
)
def test_the_floor_is_the_same_real_distance_at_every_scale(metres_per_unit, expected):
    assert tolerance_in_units(ABS_TOL_M, metres_per_unit) == pytest.approx(expected)


def test_millimetres_keep_the_old_number_exactly():
    """The previous hard-coded 2.0 was right for mm, and must not move."""
    assert tolerance_in_units(ABS_TOL_M, MM) == 2.0


def test_an_unknown_scale_falls_back_to_millimetres():
    """infer_units returns 0.0 when it finds no envelope; do not divide by it."""
    assert tolerance_in_units(ABS_TOL_M, 0.0) == tolerance_in_units(ABS_TOL_M, MM_PER_UNIT)


# --- the bug this fixes -------------------------------------------------

def test_a_metre_scale_error_no_longer_validates():
    """The 06.png case: [3.23, 1.5] = 4.73 against a stated 2.95.

    A 1.78 m error used to pass, because 1.78 < the flat floor of 2.0.
    """
    assert not validate_chain([3.23, 1.5], 2.95, metres_per_unit=M).ok


def test_the_same_relative_error_fails_at_every_scale():
    """It always failed in millimetres. Now it fails in metres too."""
    assert not validate_chain([3230, 1500], 2950, metres_per_unit=MM).ok
    assert not validate_chain([3.23, 1.5], 2.95, metres_per_unit=M).ok


def test_a_genuine_close_still_passes_in_metres():
    assert validate_chain([1.45, 1.5], 2.95, metres_per_unit=M).ok


def test_hand_drawn_rounding_still_passes_in_millimetres():
    """318+360+215+132 = 1025 against a stated 1026 - the reason for a tolerance."""
    assert validate_chain([318, 360, 215, 132], 1026, metres_per_unit=MM).ok


# --- drop_cumulative carried the same bug ------------------------------

def test_cumulative_detection_is_scaled_too():
    """A flat 1.0 tolerance would eat real segments off a metre-scale plan.

    On [3.0, 3.5] nothing is a running total: 3.5 is not 3.0. In metres a
    1.0 floor would call it one anyway.
    """
    kept, dropped = drop_cumulative([3.0, 3.5], metres_per_unit=M)
    assert kept == [3.0, 3.5]
    assert dropped == []


def test_a_real_running_total_is_still_dropped_in_metres():
    kept, dropped = drop_cumulative([3.0, 3.5, 6.5], metres_per_unit=M)
    assert kept == [3.0, 3.5]
    assert dropped == [6.5]


def test_cumulative_detection_is_unchanged_in_millimetres():
    kept, dropped = drop_cumulative([300, 350, 650], metres_per_unit=MM)
    assert kept == [300, 350]
    assert dropped == [650]


# --- the reader-side floor ---------------------------------------------

def test_match_chain_floor_is_scaled():
    """_match_chain runs before unit inference, so it takes the scale too."""
    chain = [_Box(3.23), _Box(1.5)]
    assert _match_chain(chain, 2.95, MM) is not None   # 2.0 floor swallows it
    assert _match_chain(chain, 2.95, M) is None        # 0.002 floor does not


class _Box:
    """Minimal stand-in for a TextBox: _match_chain only reads .value."""

    def __init__(self, value: float):
        self.value = value


# --- title-block text is not a room ------------------------------------

def test_the_title_block_scale_note_is_not_a_room():
    """"SCALE: 10 : 1 MTS" parses as 10 x 1 once punctuation becomes an x."""
    assert parse_rooms(["SCALE 10 : 1 MTS"]) == []


def test_a_long_corridor_is_still_a_room():
    rooms = parse_rooms(["HALLWAY 1200x300"])
    assert len(rooms) == 1


@pytest.mark.parametrize("plan", ALL_PLANS, ids=[p.key for p in ALL_PLANS])
def test_no_real_room_is_rejected_by_the_aspect_guard(plan):
    """Worst in the corpus is a 370x130 toilet at 2.85, well under the bound."""
    for room in parse_rooms(plan.room_blocks):
        assert is_plausible_room(room)
        assert max(room.width, room.length) / min(room.width, room.length) < MAX_ROOM_ASPECT


# --- regression: the millimetre and centimetre plans must not move -----

@pytest.mark.parametrize("plan", ALL_PLANS, ids=[p.key for p in ALL_PLANS])
def test_existing_plans_are_untouched_by_the_rescaling(plan):
    """Every sample is mm or cm, where the scaled floor equals the old one."""
    ex = extract_plan(
        plan.envelope_w, plan.envelope_l, plan.room_blocks, plan.chains, plan.opening_tags
    )
    assert ex.units.unit in {"mm", "cm"}
    # The point of the guard: rescaling must not break a chain that closed.
    assert all(check.ok for check in ex.chain_checks)


def test_a_metre_scale_plan_is_inferred_as_metres():
    """06.png reads around 20 m, which must land in the metre bucket."""
    assert infer_units(20.0).unit == "m"
    assert infer_units(1026).unit == "cm"
    assert infer_units(14000).unit == "mm"
    # 2295 is the sum of 06.png top chain. As mm it would be a 2.3 m
    # building, so the inference correctly reads it as centimetres.
    assert infer_units(2295).unit == "cm"
