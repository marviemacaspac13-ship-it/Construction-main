"""Reading printed tags off a plan.

The counting logic is tested against constructed boxes, so it runs fast and
the arithmetic is visible. One `ocr`-marked test reads the real plumbing
plan, because the whole reason this module exists is that a whole-page pass
finds none of its water closets.
"""

from pathlib import Path

import cv2
import pytest

from app.extract.ocr import TextBox
from app.extract.tags import (
    TagCount,
    count_tags,
    normalise_tag,
    read_tiled,
    tally,
)

PLANS = Path(__file__).parent.parent / "fixtures" / "plans"

# Fixture tags on a sanitary plan. `U` is a single character and the text
# detector does not propose it, so it is here to be counted if it ever is.
PLUMBING_TAGS = {
    "water_closet": r"WC",
    "lavatory": r"LAV",
    "urinal": r"U",
    "floor_drain": r"FD",
    "cleanout": r"C\.?O\.?",
}


def box(text: str, cx: float = 0, cy: float = 0) -> TextBox:
    return TextBox(text=text, cx=cx, cy=cy, score=0.8, rotated=False)


# --- normalising what OCR actually returns ------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [("FD", "FD"), ("+ FD", "FD"), ("FD *", "FD"), ("-FD", "FD"),
     ("wc", "WC"), ("C.O", "C.O"), (" LAV ", "LAV")],
)
def test_leader_line_marks_are_stripped(raw, expected):
    """OCR picks up the leader line beside a tag as punctuation."""
    assert normalise_tag(raw) == expected


def test_counting_is_case_insensitive_and_ignores_edge_noise():
    boxes = [box("WC"), box("wc"), box("+ WC"), box("WC *")]
    assert count_tags(boxes, PLUMBING_TAGS)["water_closet"].count == 4


# --- counting -----------------------------------------------------------

def test_every_requested_tag_comes_back_even_at_zero():
    """A caller has to tell "none on this plan" from "not looked for"."""
    counts = count_tags([box("WC")], PLUMBING_TAGS)
    assert set(counts) == set(PLUMBING_TAGS)
    assert counts["urinal"].count == 0


def test_a_tag_is_counted_once_not_per_pattern():
    """`U` must not also swallow the U in nothing else; one box, one tag."""
    counts = count_tags([box("U")], PLUMBING_TAGS)
    assert sum(c.count for c in counts.values()) == 1


def test_room_labels_and_titles_are_not_tags():
    boxes = [box("KITCHEN"), box("TO SEPTIC TANK"), box("1X75"), box("VTR")]
    assert tally(count_tags(boxes, PLUMBING_TAGS)) == {}


def test_a_partial_word_does_not_match():
    """fullmatch, not search - otherwise LAVATORY counts as LAV."""
    assert count_tags([box("LAVATORY")], PLUMBING_TAGS)["lavatory"].count == 0


def test_the_boxes_behind_a_count_are_kept():
    """So a caller can show what it found rather than just a number."""
    counts = count_tags([box("WC", 10, 20), box("WC", 90, 40)], PLUMBING_TAGS)
    assert [(b.cx, b.cy) for b in counts["water_closet"].boxes] == [(10, 20), (90, 40)]


def test_tally_drops_the_zeroes():
    assert tally(count_tags([box("FD")], PLUMBING_TAGS)) == {"floor_drain": 1}


def test_a_tag_count_is_a_value_not_a_bag_of_boxes():
    assert TagCount("wc", 3).count == 3
    assert TagCount("wc", 3).boxes == ()


# --- against the real plan ----------------------------------------------

@pytest.mark.ocr
@pytest.mark.skipif(not (PLANS / "07.png").exists(), reason="plan images not present")
def test_tiling_recovers_tags_the_whole_page_pass_misses():
    """The reason this module exists.

    A single whole-page read of `07.png` finds 0 water closets against
    roughly 13 on the drawing. Tiling finds them. Counts are asserted as
    ranges because nobody has counted the drawing by hand - this catches a
    collapse to zero or an explosion into noise, and claims nothing more.
    """
    image = cv2.imread(str(PLANS / "07.png"))
    counts = tally(count_tags(read_tiled(image), PLUMBING_TAGS))

    assert counts["water_closet"] >= 5
    assert counts["lavatory"] >= 8
    assert counts["floor_drain"] >= 8
    # Nothing should run away: the plan has tens of fixtures, not hundreds.
    assert all(n < 40 for n in counts.values())


@pytest.mark.ocr
@pytest.mark.skipif(not (PLANS / "07.png").exists(), reason="plan images not present")
def test_deduplication_is_what_makes_it_a_count():
    """Overlapping tiles see the same tag several times.

    Without merge_boxes deduplicating on text AND position, `LAV` comes
    back about 39 times against roughly 11 real ones.
    """
    image = cv2.imread(str(PLANS / "07.png"))
    merged = tally(count_tags(read_tiled(image), PLUMBING_TAGS))

    raw: list[TextBox] = []
    from app.extract.ocr import read_region
    h, w = image.shape[:2]
    for row in range(5):
        for col in range(5):
            raw += read_region(
                image, col * (w // 5), row * (h // 5),
                (col + 1) * (w // 5), (row + 1) * (h // 5),
            )
    undeduped = tally(count_tags(raw, PLUMBING_TAGS))
    assert undeduped["lavatory"] > merged["lavatory"]


# --- a legend is not a set of fixtures ----------------------------------

SHAPE = (650, 1356, 3)  # the sample water-line layout that carries a legend


def test_a_legend_row_is_not_counted():
    """`LAV  LAVATORY` in a legend table is a definition, not a lavatory.

    Left uncaught this costs a phantom fixture per row, and on a plan whose
    fixtures are too faint to read but whose legend is crisp, every count
    would come from the legend.
    """
    boxes = [box("LAV", 1161, 87), box("LAVATORY", 1260, 85)]
    assert tally(count_tags(boxes, PLUMBING_TAGS, SHAPE)) == {}


def test_the_same_tag_on_the_drawing_still_counts():
    boxes = [box("LAV", 1161, 87), box("LAVATORY", 1260, 85), box("LAV", 300, 400)]
    assert tally(count_tags(boxes, PLUMBING_TAGS, SHAPE)) == {"lavatory": 1}


def test_an_expansion_must_start_with_the_same_letter():
    """What keeps this from eating fixtures that merely sit near text."""
    boxes = [box("WC", 100, 100), box("KITCHEN", 190, 100)]
    assert tally(count_tags(boxes, PLUMBING_TAGS, SHAPE)) == {"water_closet": 1}


def test_a_duplicate_read_of_the_same_glyph_is_not_an_expansion():
    """The two OCR passes disagree on one mark: 'WC' and "wC'" at one spot.

    Both survive dedupe because the strings differ. Without a minimum gap
    the longer misread looks like an expansion and suppresses the real
    fixture - which cost three of them on the sample sanitary plan.
    """
    boxes = [box("WC", 168, 505), box("wC'", 168, 505)]
    assert tally(count_tags(boxes, PLUMBING_TAGS, SHAPE))["water_closet"] >= 1


def test_an_expansion_far_across_the_sheet_is_not_a_legend_row():
    boxes = [box("FD", 100, 100), box("FLOOR DRAIN", 1300, 100)]
    assert tally(count_tags(boxes, PLUMBING_TAGS, SHAPE)) == {"floor_drain": 1}


def test_an_expansion_on_another_line_is_not_a_legend_row():
    boxes = [box("FD", 100, 100), box("FLOOR DRAIN", 190, 400)]
    assert tally(count_tags(boxes, PLUMBING_TAGS, SHAPE)) == {"floor_drain": 1}


def test_without_an_image_shape_no_legend_suppression_is_attempted():
    """The windows are fractions of the image; with no scale, do not guess."""
    boxes = [box("LAV", 1161, 87), box("LAVATORY", 1260, 85)]
    assert tally(count_tags(boxes, PLUMBING_TAGS)) == {"lavatory": 1}


@pytest.mark.ocr
@pytest.mark.skipif(
    not (PLANS / "Data Set" / "Plumbingplan" / "IMAGE" / "01.png").exists(),
    reason="data set not present",
)
def test_the_real_legend_plan_counts_only_its_one_fixture():
    """GROUND FLOOR WATER LINE LAYOUT: a 14-row legend, one WC on the plan."""
    image = cv2.imread(str(PLANS / "Data Set" / "Plumbingplan" / "IMAGE" / "01.png"))
    boxes = read_tiled(image)
    assert tally(count_tags(boxes, PLUMBING_TAGS)) != tally(
        count_tags(boxes, PLUMBING_TAGS, image.shape)
    ), "the legend should have been suppressed"
    assert tally(count_tags(boxes, PLUMBING_TAGS, image.shape)) == {"water_closet": 1}
