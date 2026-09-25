"""The three electrical plans anybody has counted by hand.

Supplied by the project owner, read off the drawings room by room. These
are the only measurements of detector recall that exist - every other
statement about how well symbol matching works on this corpus is an
impression. Between them they set the match threshold and they are what
says whether it generalises.

`05.png` (15 Sep) - a combined lighting and power plan.

    Ceiling outlets (CLR01), 21:
        Living 5, Porch 5, Dining 3, Garden/exterior 2, Bedroom 1,
        Bedroom 2, Master, Garage, Kitchen, Toilet & Bath 1 each

    Convenience outlets (OT01), 18 - RECOUNTED 25 Sep. The first count
    said 14, including the kWh meter. A recount against a numbered overlay
    of every hit found 18 wall outlet symbols (a circle with two lines
    through it), one of them the ACU point, and the meter is not among
    them. Two hits the old crops made - a door jamb in the dining area and
    a wall line on the porch - are confirmed as NOT outlets, so the old
    claim that every detection at 0.66 was real was wrong.

`10.png` (24 Sep) - a POWER layout by a third draughtsman, clean CAD at
0.44 MP. Convenience outlets 14, ceiling outlets none - it draws no
lights, so any CLR01 here is a false hit.

`08.png` (15 Sep) - a LIGHTING-ONLY layout, circles joined by dashed
switch legs. It carries no convenience outlets at all, which is what makes
it the useful second sample: anything matched as `OT01` here is a
mislabel, so it measures precision in a way `05.png` cannot.

    Ceiling outlets, 19:
        Exterior and perimeter 7 - top-left corner, 2 in the carport, 1
        below it, 1 in the porch, top-right and bottom-right corners
        Interior 12 - 2 top-left room, 4 centre living/dining, 1 top-right
        bedroom, 1 centre-right hallway, 1 bottom-right bedroom, 2 small
        utility spaces, 1 below the centre

    Convenience outlets: none.

These are LOWER bounds on recall and UPPER bounds on the count. A detector
that finds more than the hand count has started matching noise, which is
the failure this corpus is most prone to.
"""

from collections import Counter
from math import dist
from pathlib import Path

import pytest

from app.vision.preprocess import preprocess_image
from app.vision.template_match import match_templates

PLANS = Path(__file__).parent / "fixtures" / "plans"
COMBINED = PLANS / "05.png"
LIGHTING = PLANS / "Data Set" / "Electricalplan" / "IMAGE" / "08.png"
POWER = PLANS / "Data Set" / "Electricalplan" / "IMAGE" / "10.png"

COMBINED_CEILING, COMBINED_CONVENIENCE = 21, 18
LIGHTING_CEILING, LIGHTING_CONVENIENCE = 19, 0
POWER_CEILING, POWER_CONVENIENCE = 0, 14

pytestmark = pytest.mark.ocr


def detect(path: Path):
    return match_templates(preprocess_image(path.read_bytes()))


@pytest.fixture(scope="module")
def combined():
    if not COMBINED.exists():
        pytest.skip("plan image not present")
    return detect(COMBINED)


@pytest.fixture(scope="module")
def lighting():
    if not LIGHTING.exists():
        pytest.skip("data set not present")
    return detect(LIGHTING)


@pytest.fixture(scope="module")
def power():
    if not POWER.exists():
        pytest.skip("data set not present")
    return detect(POWER)


def centres(detections):
    return [((d.bbox[0] + d.bbox[2]) / 2, (d.bbox[1] + d.bbox[3]) / 2) for d in detections]


# --- 05.png, the combined plan ------------------------------------------

def test_combined_no_count_exceeds_the_hand_count(combined):
    """Over the truth means noise, the cheaper failure to hit."""
    counts = Counter(d.label for d in combined)
    assert counts["CLR01"] <= COMBINED_CEILING
    assert counts["OT01"] <= COMBINED_CONVENIENCE


def test_combined_ceiling_outlet_recall(combined):
    """15 of 21 at the threshold this was measured at."""
    counts = Counter(d.label for d in combined)
    assert counts["CLR01"] / COMBINED_CEILING >= 0.70


def test_combined_convenience_outlet_recall(combined):
    """16 of 18, with no false hits among them.

    The old crops, cut from this very sheet, found 13 - of which 2 were a
    door jamb and a wall line. The duplex crops that replaced them come
    from a textbook legend, not from this drawing, and do better on it.
    """
    counts = Counter(d.label for d in combined)
    assert counts["OT01"] / COMBINED_CONVENIENCE >= 0.85


# --- 08.png, the lighting-only plan -------------------------------------

def test_lighting_every_symbol_on_the_sheet_is_found(lighting):
    """17 distinct locations against 19 drawn, every one labelled right.

    This plan was called a false pass before anyone counted it: 17 ceiling
    outlets on a 0.17 MP sheet looked like noise clearing the floor. It was
    not. Nothing distinguished it from a bad read by count or density, and
    only counting could tell.

    It used to find all 19 - but 2 of them only through the old wall-outlet
    crop, which labelled those lights as outlets. That same crop made the
    two false hits on 05.png. Replacing it (25 Sep) traded 2 real-but-
    mislabelled finds here for 2 false finds there, and the labels on this
    sheet are now all correct.
    """
    found = centres(lighting)
    distinct = [
        c for i, c in enumerate(found)
        if all(dist(c, other) >= 12 for other in found[:i])
    ]
    assert len(distinct) >= LIGHTING_CEILING * 0.85


def test_lighting_ceiling_outlet_recall(lighting):
    """17 of 19 correctly labelled. Second drawing, same threshold."""
    counts = Counter(d.label for d in lighting)
    assert counts["CLR01"] / LIGHTING_CEILING >= 0.85


def test_lighting_convenience_outlets_are_mislabels_and_stay_few(lighting):
    """A lighting layout has none, so every OT01 here is a wrong label.

    The old outlet crops put 2 here; the duplex crops put none, because a
    circle with two lines through it does not look like a plain ceiling
    circle. Up to 3 is tolerated; a drift upward means the labels have
    stopped meaning anything.
    """
    counts = Counter(d.label for d in lighting)
    assert counts["OT01"] <= 3


# --- 10.png, the power layout ---------------------------------------------

def test_power_outlets_are_found_on_a_third_drawing(power):
    """9 of 14. It was 0 of 14 with crops cut from 05.png.

    The five missed are mostly the outlets carrying a label beside them
    (ACU, REF, R), where the text touches the symbol. Every one of the 9
    was checked by eye and sits on a real outlet.
    """
    counts = Counter(d.label for d in power)
    assert counts["OT01"] <= POWER_CONVENIENCE
    assert counts["OT01"] / POWER_CONVENIENCE >= 0.6


def test_power_ceiling_hits_are_known_false_and_stay_few(power):
    """This sheet draws no lights, so every CLR01 here is wrong - today 4.

    Two are gridline bubbles in the left margin, where the grid line
    through the circle looks like the cross of a ceiling outlet; the others
    sit on a column and in the dining area. They are a known error, priced
    as real, and this pins them so they cannot quietly grow.
    """
    counts = Counter(d.label for d in power)
    assert counts["CLR01"] <= 4


# --- all three ------------------------------------------------------------

def test_every_counted_plan_clears_the_pricing_floor(combined, lighting, power):
    """Or the plans that demonstrably read would start being refused."""
    from app.main import MIN_DEVICES

    assert len(combined) >= MIN_DEVICES
    assert len(lighting) >= MIN_DEVICES
    assert len(power) >= MIN_DEVICES
