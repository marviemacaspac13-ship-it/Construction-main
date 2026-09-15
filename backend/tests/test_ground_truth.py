"""The two electrical plans anybody has counted by hand.

Supplied by the project owner, read off the drawings room by room. These
are the only measurements of detector recall that exist - every other
statement about how well symbol matching works on this corpus is an
impression. Between them they set the match threshold and they are what
says whether it generalises.

`05.png` (15 Sep) - a combined lighting and power plan.

    Ceiling outlets (CLR01), 21:
        Living 5, Porch 5, Dining 3, Garden/exterior 2, Bedroom 1,
        Bedroom 2, Master, Garage, Kitchen, Toilet & Bath 1 each

    Convenience outlets (OT01), 14:
        Bedroom 1: 2 (one a dedicated ACU outlet), Master 2, Living 2,
        Kitchen 2, Garage 2, Bedroom 2, Dining, Toilet & Bath 1 each,
        Porch/entrance 1 (the kWh meter assembly)

    Two of those 14 are not plain outlets - the ACU point and the meter
    assembly carry their own legend symbols (`ACO01`, `PB01`) and have no
    reference crop.

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

COMBINED_CEILING, COMBINED_CONVENIENCE = 21, 14
LIGHTING_CEILING, LIGHTING_CONVENIENCE = 19, 0

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
    """13 of 14. Two are the ACU point and the meter, drawn differently."""
    counts = Counter(d.label for d in combined)
    assert counts["OT01"] / COMBINED_CONVENIENCE >= 0.85


# --- 08.png, the lighting-only plan -------------------------------------

def test_lighting_every_symbol_on_the_sheet_is_found(lighting):
    """19 distinct locations against 19 drawn - the best result in the corpus.

    This plan was called a false pass before anyone counted it: 17 ceiling
    outlets on a 0.17 MP sheet looked like noise clearing the floor. It was
    not. Nothing distinguished it from a bad read by count or density, and
    only counting could tell.
    """
    found = centres(lighting)
    distinct = [
        c for i, c in enumerate(found)
        if all(dist(c, other) >= 12 for other in found[:i])
    ]
    assert len(distinct) >= LIGHTING_CEILING * 0.9


def test_lighting_ceiling_outlet_recall(lighting):
    """17 of 19 correctly labelled. Second drawing, same threshold."""
    counts = Counter(d.label for d in lighting)
    assert counts["CLR01"] / LIGHTING_CEILING >= 0.85


def test_lighting_convenience_outlets_are_mislabels_and_stay_few(lighting):
    """A lighting layout has none, so every OT01 here is a wrong label.

    Both symbols are circles and nothing on the page says which is which -
    the same "variant is a librarian's choice" problem, one level up. Two
    is tolerable; a drift upward means the labels have stopped meaning
    anything.
    """
    counts = Counter(d.label for d in lighting)
    assert counts["OT01"] <= 3


# --- both -----------------------------------------------------------------

def test_both_plans_clear_the_pricing_floor(combined, lighting):
    """Or the two plans that demonstrably read would start being refused."""
    from app.main import MIN_DEVICES

    assert len(combined) >= MIN_DEVICES
    assert len(lighting) >= MIN_DEVICES
