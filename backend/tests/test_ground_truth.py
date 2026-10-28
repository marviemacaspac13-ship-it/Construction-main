"""The three electrical plans anybody has counted by hand.

Supplied by the project owner, read off the drawings room by room. These
are the only measurements of detector recall that exist - every other
statement about how well symbol matching works on this corpus is an
impression. Between them they set the match threshold and they are what
says whether it generalises.

`05.png` (recount 13 Oct) - a combined lighting and power plan.

    Visible light points, 23 (provisional visual recount):
        Bedroom 1 1, Bedroom 2 2, Dining 3, Toilet & Bath 1,
        Kitchen 2, Garage 1, Master 1, Living 3,
        Garden/exterior run 4, Porch 5.
    The earlier count was 21. The owner marked six missed light points and
    two missed convenience outlets on the detector overlay. All 33 current
    detector hits were visually inspected by Codex on 13 Oct, without an
    independent second annotator; see datasets/electrical-audit/VISUAL_REVIEW_05.md.

    Convenience outlets (OT01), 18 - RECOUNTED 25 Sep. The first count
    said 14, including the kWh meter. A recount against a numbered overlay
    of every hit found 18 wall outlet symbols (a circle with two lines
    through it), one of them the ACU point, and the meter is not among
    them. Two hits the old crops made - a door jamb in the dining area and
    a wall line on the porch - are confirmed as NOT outlets, so the old
    claim that every detection at 0.66 was real was wrong.
    The 13 Oct marked overlay identifies two current outlet misses: the
    master's bedroom east wall and the porch right wall, consistent with 18.

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

COMBINED_CEILING, COMBINED_CONVENIENCE = 23, 18
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
    """Guard against a count exceeding the provisional visual recount."""
    counts = Counter(d.label for d in combined)
    assert counts["CLR01"] <= COMBINED_CEILING
    assert counts["OT01"] <= COMBINED_CONVENIENCE


def test_combined_ceiling_outlet_recall(combined):
    """17 of 23 after the supplied appendix crop (11 Oct; denominator recounted 13 Oct).

    The new location is checked separately below: matching a total alone
    would allow a false positive to conceal a missed light.
    """
    counts = Counter(d.label for d in combined)
    assert counts["CLR01"] >= 17


def test_supplied_appendix_recovers_the_living_area_corner_light(combined):
    """Hand-checked circle at the lower-left of the living-area circuit."""
    lights = [d for d in combined if d.label == "CLR01"]
    assert any(dist(c, (315.5, 295.5)) < 5 for c in centres(lights))


def test_supplied_appendix_does_not_price_bedroom_text_as_a_light():
    """Rejected crop orientations read the O in BEDROOM 2 and crossed MIN_DEVICES.

    A 13 Oct whole-sheet visual count found nine genuine lights, all currently
    matched. The sheet is nevertheless refused by the ten-device minimum;
    that limit protects other sparse false matches and is not an accuracy
    score for this particular sheet.
    """
    path = PLANS / "Data Set" / "Electricalplan" / "IMAGE" / "11.png"
    if not path.exists():
        pytest.skip("data set not present")
    detections = detect(path)
    assert len(detections) < 10
    assert all(dist(c, (210.5, 232.5)) >= 12 for c in centres(detections))


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
    """19 of 19, every hit checked against the drawing (27 Sep 2026).

    The history is a warning about totals. For weeks this sheet "found" 17
    against 19 and was recorded as its best read. Checking each hit showed
    10 of the 17 were bare crossings of two thin lines, and only 7 were
    lights: the false hits were covering for 12 real lights the crossed-
    circle crop never matched, because this draughtsman draws a circle with
    short ticks OUTSIDE it. The ring check removed the crossings; the
    pendant-fixture legend crop, which is drawn exactly that way, found the
    12. A count that matches the truth proves nothing on its own.
    """
    found = centres(lighting)
    distinct = [
        c for i, c in enumerate(found)
        if all(dist(c, other) >= 12 for other in found[:i])
    ]
    assert len(distinct) >= LIGHTING_CEILING * 0.85


def test_lighting_ceiling_outlet_recall(lighting):
    """19 of 19, and never more: over the truth would mean a false hit."""
    counts = Counter(d.label for d in lighting)
    assert LIGHTING_CEILING - 1 <= counts["CLR01"] <= LIGHTING_CEILING


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

    The five missed locations were recorded on 13 Oct: bedroom/dining
    partition, ACU, REF, R and lower kitchen wall. The REF symbol is partly
    obscured by nearby drawing content. Every one of the 9 detected hits
    was checked by eye and sits on a real outlet.
    """
    counts = Counter(d.label for d in power)
    assert counts["OT01"] <= POWER_CONVENIENCE
    assert counts["OT01"] / POWER_CONVENIENCE >= 0.6


def test_power_sheet_has_no_false_lights(power):
    """This sheet draws no lights, so any CLR01 here is wrong - now none.

    There used to be 4, recorded as gridline bubbles. Checked hit by hit
    on 27 Sep they were not: three were plain crossings of two thin lines
    and one the corner of the word DINING, with no circle at all. The ring
    check in template_match.py removes exactly that.
    """
    counts = Counter(d.label for d in power)
    assert counts["CLR01"] == 0


# --- all three ------------------------------------------------------------

def test_the_well_read_plans_clear_the_pricing_floor(combined, lighting):
    """Or the plans that demonstrably read would start being refused."""
    from app.main import MIN_DEVICES

    assert len(combined) >= MIN_DEVICES
    assert len(lighting) >= MIN_DEVICES


def test_the_power_plan_is_refused_not_priced_short(power):
    """9 of 14 outlets is under the floor, and it stays refused.

    It priced until 27 Sep only because 4 false "lights" lifted it from 9
    to 13. With them gone, a price would be about a third short. Decided
    by the owner on 27 Sep 2026: refuse it rather than lower MIN_DEVICES.
    If recall here improves past the floor, this test is meant to fail -
    update it then.
    """
    from app.main import MIN_DEVICES

    assert len(power) < MIN_DEVICES
