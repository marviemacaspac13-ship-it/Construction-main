"""The one electrical plan anybody has counted by hand.

Supplied by the project owner on 15 Sep 2026, read off `05.png` room by
room. It is the only measurement of detector recall that exists - every
other statement about how well symbol matching works on this corpus is an
impression.

    Ceiling outlets (CLR01), 21:
        Living 5, Porch 5, Dining 3, Garden/exterior 2, Bedroom 1,
        Bedroom 2, Master, Garage, Kitchen, Toilet & Bath 1 each

    Convenience outlets (OT01), 14:
        Bedroom 1: 2 (one a dedicated ACU outlet), Master 2, Living 2,
        Kitchen 2, Garage 2, Bedroom 2, Dining, Toilet & Bath 1 each,
        Porch/entrance 1 (the kWh meter assembly)

Two of those 14 are not really plain outlets - the ACU point and the meter
assembly carry their own symbols in the legend (`ACO01`, `PB01`) and have
no reference crop. They are counted here as the owner counted them, and
the shortfall they cause is part of what the recall bounds below allow for.

These are LOWER bounds on recall and UPPER bounds on the count. A detector
that finds more than the hand count has started matching noise, which is
the failure this corpus is most prone to.
"""

from collections import Counter
from pathlib import Path

import cv2
import pytest

from app.vision.preprocess import preprocess_image
from app.vision.template_match import match_templates

PLAN = Path(__file__).parent / "fixtures" / "plans" / "05.png"

TRUE_CEILING_OUTLETS = 21
TRUE_CONVENIENCE_OUTLETS = 14

pytestmark = [
    pytest.mark.ocr,
    pytest.mark.skipif(not PLAN.exists(), reason="plan image not present"),
]


@pytest.fixture(scope="module")
def counts() -> Counter:
    image = preprocess_image(PLAN.read_bytes())
    return Counter(d.label for d in match_templates(image))


def test_no_count_exceeds_the_hand_count(counts):
    """Over the truth means noise, and noise is the cheaper failure to hit."""
    assert counts["CLR01"] <= TRUE_CEILING_OUTLETS
    assert counts["OT01"] <= TRUE_CONVENIENCE_OUTLETS


def test_ceiling_outlet_recall(counts):
    """15 of 21 at the threshold this was measured at."""
    assert counts["CLR01"] / TRUE_CEILING_OUTLETS >= 0.70


def test_convenience_outlet_recall(counts):
    """13 of 14. Two are the ACU point and the meter, drawn differently."""
    assert counts["OT01"] / TRUE_CONVENIENCE_OUTLETS >= 0.85


def test_the_plan_clears_the_pricing_floor(counts):
    """It has to, or the one good electrical plan starts being refused."""
    from app.main import MIN_DEVICES

    assert counts["CLR01"] + counts["OT01"] >= MIN_DEVICES
