"""Band resolution: how one edge of a drawing becomes a total plus a checksum.

Fast, synthetic counterparts to the image tests - a band is just numbers at
coordinates, so it can be built by hand and run without OCR.

The rule under test: a dimension chain closing on a printed overall is the
good case. When it does not close, the printed overall still beats the chain
sum, because the overall is one read of one number while the chain is many
reads and a missed segment can only make it too short. The total is
corrected and the chain goes out unclosed so the gap gets reported.
"""

import pytest

from app.extract.ocr import TextBox
from app.extract.reader import LINE_TOLERANCE, _overall_above, _resolve_band


def box(text: str, cx: float, cy: float, score: float = 0.8) -> TextBox:
    return TextBox(text=text, cx=cx, cy=cy, score=score, rotated=False)


def top_band(chain: list[tuple[str, float]], singles: list[tuple[str, float]]):
    """A top band: chain boxes on one row, each single on a row of its own."""
    boxes = [box(t, cx, 100.0) for t, cx in chain]
    for i, (t, cx) in enumerate(singles):
        boxes.append(box(t, cx, 100.0 + (i + 1) * (LINE_TOLERANCE + 10)))
    return boxes


# --- the good case ------------------------------------------------------

def test_a_chain_that_closes_on_its_overall_is_closed_and_stated():
    band = _resolve_band("top", top_band([("390", 10), ("440", 60)], [("830", 35)]))
    assert band.total == 830
    assert band.segments == [390.0, 440.0]
    assert band.stated and band.closed


def test_junk_on_the_line_is_dropped_to_make_the_chain_close():
    band = _resolve_band(
        "top", top_band([("390", 10), ("7", 30), ("440", 60)], [("830", 35)])
    )
    assert band.segments == [390.0, 440.0]
    assert band.closed


# --- the fix: an incomplete chain against a printed overall -------------

def test_a_printed_overall_beats_an_incomplete_chain():
    """The notebook plan in miniature: 390 + 370 = 760 against a stated 830."""
    band = _resolve_band("top", top_band([("390", 10), ("370", 60)], [("830", 35)]))
    assert band.total == 830
    assert band.stated


def test_the_corrected_total_is_not_reported_as_verified():
    """It is the better answer, not a proven one - closed must stay False."""
    band = _resolve_band("top", top_band([("390", 10), ("370", 60)], [("830", 35)]))
    assert not band.closed
    # The segments stay as read, so the checksum can report the gap.
    assert band.segments == [390.0, 370.0]


def test_without_an_overall_the_chain_sum_is_all_there_is():
    band = _resolve_band("top", top_band([("390", 10), ("370", 60)], []))
    assert band.total == 760
    assert not band.stated and not band.closed


# --- guards on believing a single -------------------------------------

def test_a_single_below_the_chain_sum_is_not_an_overall():
    """A chain cannot lose segments into a number smaller than itself."""
    band = _resolve_band("top", top_band([("390", 10), ("370", 60)], [("700", 35)]))
    assert band.total == 760
    assert not band.stated


def test_a_single_the_chain_barely_covers_is_not_believed():
    """760 is not a broken reading of 5000; it is a different number."""
    assert _overall_above([5000.0], 760.0) is None


def test_the_closest_overall_above_wins():
    """Pick the one leaving the smallest unexplained remainder."""
    assert _overall_above([830.0, 900.0], 760.0) == 830.0


def test_coverage_is_measured_against_each_candidate():
    """Half of 830 is 415, half of 900 is 450.

    400 reaches neither, so nothing is believed. 430 reaches 830 but not
    900, so 830 wins and 900 is rejected on its own.
    """
    assert _overall_above([830.0, 900.0], 400.0) is None
    assert _overall_above([830.0, 900.0], 430.0) == 830.0
    assert _overall_above([900.0], 430.0) is None


# --- unclosed bands must not validate anything else --------------------

def test_an_unclosed_band_is_still_usable_as_a_total():
    band = _resolve_band("top", top_band([("390", 10), ("370", 60)], [("830", 35)]))
    assert band.total == 830


def test_low_confidence_boxes_are_ignored_entirely():
    boxes = top_band([("390", 10), ("370", 60)], [("830", 35)])
    boxes.append(box("999", 80, 100.0, score=0.2))
    band = _resolve_band("top", boxes)
    assert band.segments == [390.0, 370.0]


def test_an_empty_band_resolves_to_nothing():
    band = _resolve_band("top", [])
    assert band.total is None
    assert band.segments is None
    assert not band.stated and not band.closed


def test_a_band_of_only_singles_has_no_chain_to_resolve():
    """Out of scope today: a lone printed overall with no chain is not used."""
    band = _resolve_band("top", top_band([], [("830", 35)]))
    assert band.total is None


# --- left/right bands cluster on the other axis ------------------------

def test_a_side_band_clusters_by_x_instead_of_y():
    boxes = [box("420", 50, 10), box("930", 50, 60), box("1350", 90, 35)]
    band = _resolve_band("left", boxes)
    assert band.total == 1350
    assert band.closed
    assert band.segments == [420.0, 930.0]


@pytest.mark.parametrize("name", ["top", "bottom", "left", "right"])
def test_every_band_resolves_the_same_way(name):
    """A chain runs along the edge; the overall sits off it on the other axis.

    Top and bottom chains share a y and vary in x, left and right the
    reverse, which is the only thing that differs between the four.
    """
    off_line = 100.0 + LINE_TOLERANCE + 10
    if name in ("top", "bottom"):
        boxes = [box("390", 10, 100.0), box("440", 60, 100.0), box("830", 35, off_line)]
    else:
        boxes = [box("390", 100.0, 10), box("440", 100.0, 60), box("830", off_line, 35)]
    band = _resolve_band(name, boxes)
    assert band.total == 830
    assert band.closed
    assert band.segments == [390.0, 440.0]
