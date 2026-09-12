"""The detection path, against a real electrical plan.

Until the symbol library existed, this half of the product had never run
against a real drawing - every detection test used synthetic fixtures. This
file is the first thing that exercises image -> template match -> rules ->
priced estimate on `05.png`.

There is no ground truth for symbol counts, so nothing here asserts that
the counts are RIGHT. What it pins is that the pipeline joins up, that the
rules derive what follows from a count, and that an assumed variant admits
to being one. Counts are asserted as ranges, to catch a collapse to zero or
an explosion into noise without pretending to an accuracy nobody measured.
"""

from collections import Counter
from pathlib import Path

import cv2
import pytest

from app.takeoff.from_detections import plan_from_detections, unknown_labels
from app.takeoff.estimator import estimate_plan
from app.vision.preprocess import preprocess_image
from app.vision.template_match import match_templates

PLANS = Path(__file__).parent / "fixtures" / "plans"
ELECTRICAL = PLANS / "05.png"

pytestmark = [
    pytest.mark.ocr,  # slow: multi-scale matching over a full plan
    pytest.mark.skipif(not ELECTRICAL.exists(), reason="plan images not present"),
]


@pytest.fixture(scope="module")
def detections():
    return match_templates(preprocess_image(ELECTRICAL.read_bytes()))


def test_the_library_is_not_empty():
    """Every assertion below is vacuous if no reference crops are installed."""
    from app import templates_store

    library = templates_store.list_templates()
    assert set(library) >= {"CLR01", "OT01"}
    # The outlet is drawn rotated to suit its wall, and matchTemplate is not
    # rotation-invariant, so one crop per orientation is required.
    assert len(library["OT01"]) >= 2


def test_symbols_are_found_on_a_real_plan(detections):
    counts = Counter(d.label for d in detections)
    assert counts["CLR01"] > 0, "no ceiling outlets matched"
    assert counts["OT01"] > 0, "no wall outlets matched"


def test_the_count_is_plausible_rather_than_noise(detections):
    """A bungalow has tens of outlets, not hundreds.

    The match threshold has a cliff just below its current 0.72: at 0.60 the
    same plan yields 78 detections and at 0.50 it yields 768, nearly all of
    them wall hatching and door swings. This is the guard against someone
    lowering it to chase recall.
    """
    assert 5 <= len(detections) <= 60


def test_every_detection_maps_to_a_catalog_sku(detections):
    """A label with no UnitSpec is matched and then silently dropped."""
    assert unknown_labels(detections) == []


def test_the_two_labels_do_not_claim_the_same_symbol(detections):
    """NMS is per-label, so nothing stops both templates firing on one circle."""

    def iou(a, b):
        ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
        ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if not inter:
            return 0.0
        area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
        return inter / area

    ceiling = [d for d in detections if d.label == "CLR01"]
    wall = [d for d in detections if d.label == "OT01"]
    assert not [(a, b) for a in ceiling for b in wall if iou(a.bbox, b.bbox) > 0.3]


def test_preprocessing_does_not_lose_symbols(detections):
    """Denoise plus CLAHE should help the match, or at least not hurt it."""
    raw = match_templates(cv2.imread(str(ELECTRICAL)))
    assert len(detections) >= len(raw)


# --- through the rules --------------------------------------------------

def test_the_plan_prices_end_to_end(catalog, detections):
    plan = plan_from_detections(detections, "Electrical Plan")
    result = estimate_plan(plan, catalog)
    assert result.unpriced == []
    assert result.grand_total > 0


def test_the_rules_supply_what_a_count_implies(catalog, detections):
    """Where the two paths meet: detection counts outlets, rules add boxes.

    Neither box is ever detected - there is no drawn symbol for one - so a
    template for them would double-count.
    """
    plan = plan_from_detections(detections, "Electrical Plan")
    result = estimate_plan(plan, catalog)
    by_item = {li.item_id: li for li in result.line_items}

    assert by_item["UTB01"].quantity == by_item["OT01"].quantity
    assert by_item["JCB01"].quantity == by_item["CLR01"].quantity
    assert by_item["UTB01"].rule == "electrical.utility_boxes"


def test_an_assumed_variant_says_so(catalog, detections):
    """OT01 would otherwise read as though the plan specified 1-gang."""
    plan = plan_from_detections(detections, "Electrical Plan")
    result = estimate_plan(plan, catalog)
    assert any("symbol matching" in a.lower() for a in result.assumptions)


def test_a_read_plan_carries_no_such_caveat(catalog):
    """The note belongs to detection, not to every estimate."""
    from app.extract.to_plan import extract_plan, to_plan_schema
    from tests.fixtures.sample_plans import KERALA

    schema = to_plan_schema(
        extract_plan(
            KERALA.envelope_w, KERALA.envelope_l, KERALA.room_blocks,
            KERALA.chains, KERALA.opening_tags,
        )
    )
    result = estimate_plan(schema, catalog)
    assert not any("symbol matching" in a.lower() for a in result.assumptions)
