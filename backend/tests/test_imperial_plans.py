"""A plan in feet and inches is refused, never priced.

`Data Set/Floorplan/images/` holds 2,640 US marketing floor plans with a
CSV of their square footage - downloaded house plans, which is exactly
where a stranger's drawing comes from. They are dimensioned `13-2x17-2`
and `16'-0" x 16'-0"`, and several carry no margin chains at all.

The reader already fails safely on them: the notation never parses into a
dimension, so no envelope is found, confidence is 0.0 and the route
returns 422. **That is emergent behaviour, not a guarantee** - it falls
out of the metric parser not recognising a foot mark, and someone making
the parser more forgiving could turn it into a confident wrong answer
without noticing. A US house priced against a Philippine catalog in pesos
would be wrong in every line while looking entirely plausible.

This file is what makes it a guarantee.

The dataset is NOT otherwise useful here and that is worth recording so
nobody re-evaluates it:

* **Not training data.** No bounding boxes around symbols, so it cannot
  train the detector that would replace template matching.
* **Not estimate validation.** Its `Square Feet` is living area; the
  reader computes an envelope bounding box. On `0_1.jpg` that is 3,041
  against 94ft x 55ft = 5,170 - different quantities.
* **Not room-count validation.** Measured on 30 random plans, matching
  detected bedroom labels against the CSV `Beds` column: 27% exact, 53%
  within one. Duplicate reads inflate counts and several plans return no
  rooms at all.
"""

import csv
from pathlib import Path

import pytest

from app.extract.reader import read_plan_bytes
from app.extract.units_infer import IMPERIAL_MIN_HITS, looks_imperial

DATA = Path(__file__).parent / "fixtures" / "plans" / "Data Set" / "Floorplan"
IMAGES = DATA / "images"
DETAILS = DATA / "house_plans_details.csv"

FOOT = "'"
INCH = '"'


# --- the notation, without touching an image ----------------------------

@pytest.mark.parametrize(
    "texts",
    [
        ["13-2x17-2", "18-0x17-9"],                 # feet-inches, no marks
        [f"16{FOOT}-0{INCH}", f"94{FOOT}"],         # foot and inch marks
        [f"31-3{INCH} x 47-6{INCH}", f"10-0{INCH} ceiling"],
        # What the corpus actually yields: the separator repair turns
        # `13-2x17-2` into `13x2x17x2` before anything sees it, so the
        # four-part form is the one that fires in practice.
        ["13x2x17x2", "18x0x17x9"],
    ],
)
def test_imperial_notation_is_recognised(texts):
    assert looks_imperial(texts)


@pytest.mark.parametrize(
    "texts",
    [
        ["324x240", "1026", "14000", "KITCHEN"],    # the real corpus
        ["324x240", "370x130"],                     # two parts, never four
        ["3.45", "20.00", "2.95"],                  # the metre-scale plan
        [f"MASTER{FOOT}S BEDROOM", "KITCHEN"],      # one stray apostrophe
        [],
    ],
)
def test_metric_and_noise_are_not_mistaken_for_imperial(texts):
    assert not looks_imperial(texts)


def test_one_hit_is_not_enough():
    """A single mark is an apostrophe in a room name; a drawing dimensioned
    this way carries one per room."""
    assert IMPERIAL_MIN_HITS >= 2
    assert not looks_imperial([f"94{FOOT}"])


# --- against the real sheets --------------------------------------------

def _sample(n: int) -> list[Path]:
    if not DETAILS.exists():
        return []
    with DETAILS.open(encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    paths = [DATA / r["Image Path"].replace("\\", "/") for r in rows]
    existing = [p for p in paths if p.exists()]
    # Spread across the set rather than taking the first n, which are all
    # from one source directory.
    step = max(1, len(existing) // n)
    return existing[::step][:n]


@pytest.mark.ocr
@pytest.mark.skipif(not IMAGES.exists(), reason="imperial data set not present")
@pytest.mark.parametrize("plan", _sample(6), ids=lambda p: p.name)
def test_an_imperial_plan_is_never_read_as_metric(plan: Path):
    """The guarantee. No envelope, no confidence, nothing invented.

    A plan that produced an envelope here would be pricing a US house in
    pesos off a misparsed dimension.
    """
    extraction = read_plan_bytes(plan.read_bytes())

    assert extraction.envelope_w_m == 0.0
    assert extraction.envelope_l_m == 0.0
    assert extraction.confidence == 0.0
    # Room LABELS do read - it is only the dimensions that do not - so any
    # room that came back must carry no size rather than a wrong one.
    assert all(r.width == 0.0 and r.length == 0.0 for r in extraction.rooms_m)


@pytest.mark.ocr
@pytest.mark.skipif(not IMAGES.exists(), reason="imperial data set not present")
def test_the_refusal_names_the_cause():
    """Otherwise the reader sends someone hunting for a better scan of a
    drawing that was never readable."""
    plans = _sample(4)
    flagged = [p for p in plans if read_plan_bytes(p.read_bytes()).looks_imperial]
    assert flagged, "no sampled US plan was recognised as imperial"


@pytest.mark.ocr
@pytest.mark.skipif(not IMAGES.exists(), reason="imperial data set not present")
def test_the_metric_corpus_is_not_flagged():
    """The guard must not fire on the plans the reader exists to read."""
    metric = Path(__file__).parent / "fixtures" / "plans"
    for name in ("01.png", "03.png"):
        if (metric / name).exists():
            extraction = read_plan_bytes((metric / name).read_bytes())
            assert not extraction.looks_imperial, name
            assert extraction.envelope_w_m > 0, name
