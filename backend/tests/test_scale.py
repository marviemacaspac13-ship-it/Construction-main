"""The ruler: metres per pixel, per axis, cross-validated.

Phase 1 of moving TRACE from assumed to measured. Nothing consumes this
yet - it is pinned here so the next stage starts from a known quantity
rather than a hope.

**The headline finding is that the scale is not isotropic.** On `01.png`
the vertical scale is about 10% larger than the horizontal, and two
independent methods agree on that to within 2%. A single scalar would skew
every measured length by up to 10% in one direction only, which is exactly
the kind of error nothing downstream would catch.

**The gate for this phase was three of four plans cross-validated on both
axes. It was not met - the result is two of four.** All four produce a
scale on both axes; two have both axes confirmed by a second source. The
gap is not the method: `03.png` has no vertical dimension chain and
`02.jpg` no horizontal one for the fit to check itself against.

The two sources, and which turned out to be trustworthy:

* **Printed labels** - anchored to a number the draughtsman wrote. Produces
  a fit on every plan in the corpus. This is the good one.
* **Building outline** - the largest dark component. Exact on `01.png`,
  wrong by 9% on `02.jpg` and 48% on `04.jpg`, where it captures only part
  of the structure. Useful only as a disagreeing second opinion.

A third independent source would close the gate. The room dimensions are
the obvious candidate - every room prints its size and is also drawn - but
locating a room's drawn extent is Phase 2 work, so the honest position is
that Phase 1 stopped short.
"""

from pathlib import Path

import cv2
import pytest

from app.extract.ocr import TextBox, read_array
from app.extract.reader import read_plan_bytes
from app.extract.scale import (
    AGREE_TOL,
    MAX_SPREAD,
    _fit_line,
    resolve,
    scale_from_labels,
    scale_from_outline,
)

PLANS = Path(__file__).parent / "fixtures" / "plans"


def box(value: float, cx: float, cy: float) -> TextBox:
    return TextBox(text=str(int(value)), cx=cx, cy=cy, score=0.9, rotated=False)


# --- the arithmetic, with no image involved -----------------------------

def test_a_label_sits_centred_in_its_own_segment():
    """Two labels 100 px apart, segments of 2000 and 2000 units at 1 mm per
    unit: the gap covers half of each, so 2000 mm over 100 px."""
    fit = _fit_line([(2000, 0), (2000, 100), (2000, 200)], 0.001)
    assert fit is not None
    assert fit.metres_per_pixel == pytest.approx(0.02)
    assert fit.spread == pytest.approx(0.0)


def test_uneven_segments_still_fit():
    # gaps: (1000+3000)/2 = 2000 units over 100px, (3000+1000)/2 over 100px
    fit = _fit_line([(1000, 0), (3000, 100), (1000, 200)], 0.001)
    assert fit.metres_per_pixel == pytest.approx(0.02)


def test_a_chain_that_disagrees_with_itself_is_flagged():
    """A misread segment shows up as spread, which is a better filter than
    any per-read confidence score - on the real corpus a clean chain
    spreads under 11% and one containing junk spread 264%."""
    fit = _fit_line([(2000, 0), (2000, 100), (9999, 200)], 0.001)
    assert fit.spread > MAX_SPREAD


def test_two_reads_of_one_label_are_not_a_segment():
    """The two OCR passes return the same label twice at the same spot."""
    assert _fit_line([(2000, 0), (2000, 1), (2000, 100)], 0.001) is None


def test_a_line_of_two_labels_is_not_enough():
    assert _fit_line([(2000, 0), (2000, 100)], 0.001) is None


# --- combining the sources ----------------------------------------------

def test_agreement_makes_an_axis_cross_validated():
    labels = scale_from_labels([], 0.001, ())  # empty, built by hand below
    from app.extract.scale import AxisFit

    labels = {"x": AxisFit(0.0100, 0.02, "printed_labels", 4),
              "y": AxisFit(0.0110, 0.03, "printed_labels", 4)}
    outline = {"x": AxisFit(0.0101, 0.0, "outline", 0),
               "y": AxisFit(0.0111, 0.0, "outline", 0)}
    scale, how = resolve(labels, outline)
    assert scale is not None
    assert all(v.startswith("cross-validated") for v in how.values())
    assert scale.confidence == 0.9
    # The label fit wins, because it is tied to a printed number.
    assert scale.meters_per_pixel_x == pytest.approx(0.0100)


def test_disagreement_keeps_the_label_fit_but_drops_confidence():
    from app.extract.scale import AxisFit

    labels = {"x": AxisFit(0.0100, 0.02, "printed_labels", 4),
              "y": AxisFit(0.0110, 0.02, "printed_labels", 4)}
    outline = {"x": AxisFit(0.0200, 0.0, "outline", 0),   # 100% out
               "y": AxisFit(0.0111, 0.0, "outline", 0)}
    scale, how = resolve(labels, outline)
    assert scale.meters_per_pixel_x == pytest.approx(0.0100)
    assert "disagrees" in how["x"]
    assert scale.confidence < 0.9


def test_one_axis_with_no_source_yields_no_scale():
    """Half a ruler is not a ruler. A caller must not be handed a Scale it
    can only use in one direction without knowing."""
    from app.extract.scale import AxisFit

    scale, how = resolve({"x": AxisFit(0.01, 0.0, "printed_labels", 4)}, {})
    assert scale is None
    assert how["y"] == "no source"


def test_the_agreement_tolerance_is_tight():
    """Scale error squares into an area. 3% on both axes is already 6% on a
    slab, which is the largest single quantity in an estimate."""
    assert AGREE_TOL <= 0.03


# --- against the real drawings ------------------------------------------

@pytest.mark.ocr
@pytest.mark.parametrize("name", ["01.png", "03.png", "02.jpg", "04.jpg"])
def test_every_floor_plan_yields_a_scale_on_both_axes(name):
    """Four of four. The gate was about *confirmation*, not coverage."""
    path = PLANS / name
    if not path.exists():
        pytest.skip("plan image not present")
    extraction = read_plan_bytes(path.read_bytes())
    image = cv2.imread(str(path))
    metres_per_unit = extraction.units.metres_per_unit or 0.001

    scale, _ = resolve(
        scale_from_labels(read_array(image), metres_per_unit, image.shape),
        scale_from_outline(
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),
            extraction.envelope_w_m,
            extraction.envelope_l_m,
        ),
    )
    assert scale is not None, f"{name} produced no scale"
    assert scale.meters_per_pixel_x > 0 and scale.meters_per_pixel_y > 0


@pytest.mark.ocr
def test_the_anisotropy_on_01_is_real_and_about_ten_percent():
    """The finding that corrected the `Scale` model.

    Pinned as a band: it is a property of how this sheet was rasterised,
    and a change here means the image was re-exported, not that the
    building changed.
    """
    path = PLANS / "01.png"
    if not path.exists():
        pytest.skip("plan image not present")
    extraction = read_plan_bytes(path.read_bytes())
    image = cv2.imread(str(path))
    scale, how = resolve(
        scale_from_labels(read_array(image), extraction.units.metres_per_unit, image.shape),
        scale_from_outline(
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),
            extraction.envelope_w_m,
            extraction.envelope_l_m,
        ),
    )
    assert 1.05 < scale.anisotropy < 1.20
    # Both axes confirmed by a second, unrelated method.
    assert all(v.startswith("cross-validated") for v in how.values())
    assert scale.confidence == 0.9


def test_nothing_prices_from_this_yet():
    """Phase 1 produced a ruler, not a quantity.

    The gate for wiring it to money was three of four plans confirmed on
    both axes; the result was two. This is where someone wiring it in early
    finds that out.

    Checked by import rather than by grepping for a name - `frame.py`
    discusses `meters_per_pixel` in its docstring, and a comment about a
    thing is not a use of it.
    """
    import app.takeoff.frame as frame

    imported = {
        name for name in dir(frame) if not name.startswith("__")
    }
    assert "Scale" not in imported
    assert not any("scale" in n.lower() for n in imported), sorted(imported)
