"""Counting the columns a floor plan draws - app.extract.columns.

Ground truth is the drawings themselves: on the two CAD plans every solid
black square at a wall junction is a column, 16 on 01.png and 10 on
03.png, and each hit was checked against the sheet (27 Sep 2026), not
just the total. The hand sketch and the scan draw no solid squares, and
what they return must stay small enough that the frame falls back to the
spacing rather than pricing a 2-column building.
"""

from pathlib import Path

import cv2
import pytest

from app.extract.columns import count_drawn_columns
from app.takeoff.frame import plausible_column_count
from app.takeoff.params import EstimatingParams

PLANS = Path(__file__).parent / "fixtures" / "plans"
SPACING = EstimatingParams().column_spacing_m

# name, columns drawn (None: not drawn), envelope in metres
CASES = [
    ("01.png", 16, 14.0, 11.0),
    ("03.png", 10, 11.5, 10.0),
    ("02.jpg", None, 8.3, 13.5),
    ("04.jpg", None, 10.26, 10.49),
]


def _count(name: str) -> int:
    path = PLANS / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    return count_drawn_columns(cv2.imread(str(path)))


@pytest.mark.parametrize("name, drawn, w, l", [c for c in CASES if c[1]])
def test_every_drawn_column_is_found_on_the_cad_plans(name, drawn, w, l):
    assert _count(name) == drawn
    assert plausible_column_count(drawn, w, l, SPACING)


@pytest.mark.parametrize("name, drawn, w, l", [c for c in CASES if not c[1]])
def test_a_plan_that_draws_no_columns_falls_back(name, drawn, w, l):
    counted = _count(name)
    assert counted <= 2
    assert not plausible_column_count(counted, w, l, SPACING)


def test_a_blank_sheet_has_no_columns():
    import numpy as np

    assert count_drawn_columns(np.full((400, 400, 3), 255, np.uint8)) == 0
