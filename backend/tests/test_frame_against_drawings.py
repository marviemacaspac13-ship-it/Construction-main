"""Measuring the column grid off a drawing, to check the guide against it.

`frame.py` infers the whole structural frame from the envelope: columns
every `column_spacing_m` (3.5 m) around the perimeter, at the
`COLUMN_SECTION_M` (0.20 x 0.40) that `Guide.docx` specifies. Concrete and
its steel are more than half a floor-plan total and none of it is read, so
this was the largest assumption in the largest cost centre.

**It is a reasonable assumption, not an exact one**, and the correction
below is why the distinction matters. The black squares at the wall
intersections on a CAD plan ARE the columns. They can be found, and the
scale to measure them in comes free: the printed chain says the envelope
is 14000 mm and the image says how many pixels that is.

On `01.png` the detected column spacings fit the printed chain
`[3200, 3700, 3300, 3800]` to 0.3%, 2.2%, 2.5%, 0.3% - the columns sit on
the printed grid lines, which is what makes this a measurement rather than
a coincidence.

**The scale on these drawings is NOT isotropic**, and the first version of
this file missed it. Fitting one scalar to the x-chain and applying it to
both axes reported a 0.284 m square section, 3% from the guide by area.
Two independent methods - the printed-label spacing and the building
outline - both say the vertical scale is about 10% larger than the
horizontal:

    mpp_x 0.01352      mpp_y 0.01497        ratio 1.107
    labels  13.49 / 14.85 mm/px     outline  13.23 / 14.97 mm/px

so the honest measurement is:

    measured  0.284 x 0.322 = 0.0914 m2
    guide     0.20  x 0.40  = 0.0800 m2      +14%

The column is not square; it only looked square because one scale was
applied to two axes. The guide still sits within a sensible band of the
drawing and concrete is priced by volume, so `COLUMN_SECTION_M` is not
challenged by this - but "confirmed to 1%" was never true, and the
tolerance below reflects the real gap rather than the flattering one.

**Nothing here feeds a price**, deliberately. The detection works on
`01.png`, partly on `03.png`, and not at all on the two 0.6 MP scans, so it
could not replace the assumption even if the assumption were wrong. What
it does is pin the agreement, so a future change to `COLUMN_SECTION_M`
that drifts away from what the drawings actually show will fail here.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.extract.reader import read_plan_bytes
from app.takeoff.constants import COLUMN_SECTION_M
from app.takeoff.params import EstimatingParams

PLAN = Path(__file__).parent / "fixtures" / "plans" / "01.png"

# Erosion kernel: thicker than a wall line, thinner than a column. The
# squares are drawn touching the walls, so a plain connected-component pass
# swallows the entire building as one blob - eroding first is what
# separates a solid block from a thin line. The count is stable from 5x5 to
# 11x11 (16 blobs either way), so this is not a tuned number.
ERODE = 7
DARK = 100

pytestmark = [
    pytest.mark.ocr,
    pytest.mark.skipif(not PLAN.exists(), reason="plan image not present"),
]


def find_columns(gray: np.ndarray) -> list[tuple[float, float, float, float]]:
    """(cx, cy, width_px, height_px) for every solid square on the sheet."""
    eroded = cv2.erode((gray < DARK).astype(np.uint8), np.ones((ERODE, ERODE), np.uint8))
    count, _, stats, centroids = cv2.connectedComponentsWithStats(eroded, 8)
    found = []
    for i in range(1, count):
        _, _, w, h, _ = stats[i]
        w, h = w + ERODE - 1, h + ERODE - 1  # undo the erosion
        if w >= 8 and h >= 8 and 0.7 <= w / h <= 1.4:
            found.append((centroids[i][0], centroids[i][1], float(w), float(h)))
    return found


def cluster(values: list[float], tol: float) -> list[float]:
    groups: list[list[float]] = []
    for v in sorted(values):
        if not groups or v - groups[-1][-1] > tol:
            groups.append([v])
        else:
            groups[-1].append(v)
    return [float(np.mean(g)) for g in groups]


@pytest.fixture(scope="module")
def measured():
    extraction = read_plan_bytes(PLAN.read_bytes())
    gray = cv2.cvtColor(cv2.imread(str(PLAN)), cv2.COLOR_BGR2GRAY)
    columns = find_columns(gray)
    assert len(columns) >= 8, f"only {len(columns)} columns found"

    width_px = float(np.median([c[2] for c in columns]))
    height_px = float(np.median([c[3] for c in columns]))
    gx = cluster([c[0] for c in columns], width_px)
    gaps_px = [gx[i + 1] - gx[i] for i in range(len(gx) - 1)]

    # HORIZONTAL scale, from the printed chain with the same number of
    # segments as we have gaps. Fitted to the drawing rather than assuming
    # the corner columns span the envelope, which was 8-12% out.
    chain = next(
        c for c in extraction.chain_checks if len(c.kept) == len(gaps_px)
    )
    metres_per_unit = extraction.envelope_w_m / chain.stated_total
    wanted_m = [s * metres_per_unit for s in chain.kept]
    mpp_x = float(np.median([w / p for w, p in zip(wanted_m, gaps_px)]))

    # VERTICAL scale, measured separately because these drawings are not
    # isotropic. Taken from the height of the building outline - the
    # largest dark component, which on this plan tracks the outer wall
    # exactly - against the printed envelope length.
    dark = (gray < 128).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
    building = max(range(1, count), key=lambda i: stats[i][4])
    mpp_y = extraction.envelope_l_m / stats[building][3]

    return {
        "columns": columns,
        "width_m": width_px * mpp_x,
        "height_m": height_px * mpp_y,
        "gaps_m": [g * mpp_x for g in gaps_px],
        "wanted_m": wanted_m,
        "mpp_x": mpp_x,
        "mpp_y": mpp_y,
    }


def test_the_columns_sit_on_the_printed_grid(measured):
    """What makes this a measurement rather than a coincidence.

    If the detected squares were noise their spacings would not reproduce
    the dimension chain printed along the same edge.
    """
    errors = [
        abs(g - w) / w for g, w in zip(measured["gaps_m"], measured["wanted_m"])
    ]
    assert max(errors) < 0.05, f"column gaps do not match the printed chain: {errors}"


def test_the_scale_is_not_isotropic(measured):
    """The finding that corrected this file.

    Applying one scalar to both axes made the column look square and the
    guide look confirmed to 1%. Two independent methods - printed-label
    spacing and the building outline - both put the vertical scale about
    10% above the horizontal. Pinned as a range rather than a value
    because it is a property of how this sheet was rasterised, not of the
    building.
    """
    ratio = measured["mpp_y"] / measured["mpp_x"]
    assert 1.05 < ratio < 1.20, f"anisotropy {ratio:.3f} outside the measured band"


def test_the_guide_section_is_the_right_order_but_not_exact(measured):
    """0.284 x 0.322 m measured, against a 0.20 x 0.40 m guide rectangle.

    Same order, +14% by area - NOT the "<1%" the first version of this
    file claimed on a single-scale measurement. Concrete is priced by
    volume, so `COLUMN_SECTION_M` is not challenged by a gap this size on
    one plan; the tolerance is set to catch a drift that matters, not to
    flatter the guide.
    """
    guide_area = COLUMN_SECTION_M[0] * COLUMN_SECTION_M[1]
    measured_area = measured["width_m"] * measured["height_m"]
    assert abs(measured_area - guide_area) / guide_area < 0.25

    # And the shape genuinely differs: the drawn column is nearly square,
    # the guide's is 1:2. Recording it so nobody "fixes" one to match the
    # other without a second plan to argue from.
    assert measured["height_m"] / measured["width_m"] < 1.5


def test_the_assumed_spacing_sits_inside_the_real_range(measured):
    """`column_spacing_m` is 3.5. The drawing bays run 3.2 to 3.8."""
    spacing = EstimatingParams().column_spacing_m
    assert min(measured["wanted_m"]) <= spacing <= max(measured["wanted_m"])


def test_the_measurement_feeds_no_price(measured):
    """A guard on intent, not on arithmetic.

    The detection works on this plan, partly on `03.png` and not at all on
    the 0.6 MP scans, so it cannot be a pricing input. If someone wires it
    to one, `frame.py` must stop taking the section from a constant - and
    this assertion is where they will find out.
    """
    from app.takeoff import frame

    source = Path(frame.__file__).read_text(encoding="utf-8")
    assert "find_columns" not in source
    assert "COLUMN_SECTION_M" in source
