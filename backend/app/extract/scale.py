"""How many metres one pixel covers, per axis, cross-validated.

Nothing in TRACE measures pixels today - every quantity comes from printed
text. This module is the prerequisite for changing that: before a traced
wall or a measured footprint can mean anything, the drawing needs a ruler.

**Two independent sources, and a result is only trusted when they agree.**

1. *Printed labels.* Every dimension label sits centred in its own segment,
   so the gap between the centres of two consecutive labels is half of one
   segment plus half of the next. That converts directly into a scale, and
   it needs no image processing at all - only the OCR boxes that have
   already been read.
2. *The building outline.* The largest dark connected component is the wall
   structure; its bounding box against the printed envelope gives a second,
   completely different estimate.

They fail on different plans, which is the point. Measured on the corpus:
the label fit works on all four floor plans, the outline is exact on
`01.png` and misses part of the building on `04.jpg`.

**The scale is per axis because these drawings are not isotropic** - see
`Scale` in `app/takeoff/schema.py` for the measurements and for the wrong
claim a single scalar already produced.

A chain that disagrees with itself is junk, and says so loudly: a clean fit
spreads 0-11% across its segments, while one containing a misread spread
264% and another 38,771%. `MAX_SPREAD` is what rejects those, and it is a
much better filter than any confidence score on the individual reads.
"""

from dataclasses import dataclass

import numpy as np

from app.extract.ocr import TextBox
from app.takeoff.schema import Scale

# Boxes within this fraction of the image are treated as sitting on one
# dimension line. A fraction, never a pixel count - this corpus runs from
# 0.16 MP to 3.15 MP.
LINE_TOL_FRAC = 0.012

# A chain whose per-segment fits disagree by more than this contains a
# misread and is discarded whole.
MAX_SPREAD = 0.30

# Two sources must agree within this to call an axis cross-validated.
AGREE_TOL = 0.03

MIN_LABELS = 3


@dataclass(frozen=True)
class AxisFit:
    """One estimate of one axis, and how much it argued with itself."""

    metres_per_pixel: float
    spread: float
    source: str
    labels: int


def _fit_line(values: list[tuple[float, float]], metres_per_unit: float) -> AxisFit | None:
    """Fit a scale from one dimension line.

    `values` is (printed value, pixel position) for each label, in any
    order. A label is centred in its segment, so the distance between two
    consecutive label centres covers half of each.
    """
    ordered = sorted(values, key=lambda v: v[1])
    if len(ordered) < MIN_LABELS:
        return None

    fits = []
    for (v1, p1), (v2, p2) in zip(ordered, ordered[1:]):
        gap_px = abs(p2 - p1)
        if gap_px <= 3:  # two reads of the same label
            continue
        fits.append(((v1 + v2) / 2.0 * metres_per_unit) / gap_px)

    if len(fits) < 2:
        return None

    median = float(np.median(fits))
    if median <= 0:
        return None
    spread = (max(fits) - min(fits)) / median
    return AxisFit(median, spread, "printed_labels", len(ordered))


def _cluster(boxes: list[TextBox], along: str, tol: float) -> list[list[TextBox]]:
    """Group boxes sitting on a common line, without needing the bands.

    `along="x"` finds horizontal chains (labels sharing a y), which measure
    the x axis.
    """
    key = (lambda b: b.cy) if along == "x" else (lambda b: b.cx)
    groups: list[list[TextBox]] = []
    for box in sorted(boxes, key=key):
        if groups and key(box) - key(groups[-1][-1]) <= tol:
            groups[-1].append(box)
        else:
            groups.append([box])
    return groups


def scale_from_labels(
    boxes: list[TextBox], metres_per_unit: float, image_shape: tuple[int, ...]
) -> dict[str, AxisFit]:
    """Best label-derived fit per axis, or an empty dict."""
    if len(image_shape) < 2 or metres_per_unit <= 0:
        return {}
    tol = max(image_shape[0], image_shape[1]) * LINE_TOL_FRAC
    numeric = [b for b in boxes if b.is_number and (b.value or 0) > 0]

    best: dict[str, AxisFit] = {}
    for axis in ("x", "y"):
        position = (lambda b: b.cx) if axis == "x" else (lambda b: b.cy)
        for line in _cluster(numeric, axis, tol):
            fit = _fit_line([(b.value, position(b)) for b in line], metres_per_unit)
            if fit is None or fit.spread > MAX_SPREAD:
                continue
            # Prefer the line that argues with itself least; a tie goes to
            # the one built from more labels.
            current = best.get(axis)
            if current is None or (fit.spread, -fit.labels) < (current.spread, -current.labels):
                best[axis] = fit
    return best


def scale_from_outline(
    gray, envelope_w_m: float, envelope_l_m: float
) -> dict[str, AxisFit]:
    """Second opinion: the wall structure's bounding box.

    Deliberately crude. It is here to disagree with the label fit when one
    of them is wrong, not to be the answer.
    """
    import cv2

    if envelope_w_m <= 0 or envelope_l_m <= 0:
        return {}
    dark = (gray < 128).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
    if count < 2:
        return {}
    biggest = max(range(1, count), key=lambda i: stats[i][4])
    _, _, width_px, height_px, _ = stats[biggest]
    if width_px < 20 or height_px < 20:
        return {}
    return {
        "x": AxisFit(envelope_w_m / width_px, 0.0, "outline", 0),
        "y": AxisFit(envelope_l_m / height_px, 0.0, "outline", 0),
    }


def resolve(
    labels: dict[str, AxisFit], outline: dict[str, AxisFit]
) -> tuple[Scale | None, dict[str, str]]:
    """Combine the two sources into a Scale, and say how each axis was won.

    An axis is **cross-validated** when both sources agree within
    `AGREE_TOL`; the label fit is then used, because it is the one tied to
    a printed number. An axis with only one source is still returned, at
    reduced confidence, because a single ruler beats none - but the caller
    can see which is which and decline to measure with it.
    """
    chosen: dict[str, AxisFit] = {}
    how: dict[str, str] = {}

    for axis in ("x", "y"):
        a, b = labels.get(axis), outline.get(axis)
        if a and b:
            disagreement = abs(a.metres_per_pixel - b.metres_per_pixel) / a.metres_per_pixel
            if disagreement <= AGREE_TOL:
                chosen[axis] = a
                how[axis] = f"cross-validated ({disagreement:.1%} apart)"
                continue
            # They disagree. The label fit is still the better bet - it is
            # anchored to a printed number - but nothing has confirmed it.
            chosen[axis] = a
            how[axis] = f"labels only, outline disagrees by {disagreement:.0%}"
        elif a:
            chosen[axis] = a
            how[axis] = "labels only, no outline"
        elif b:
            chosen[axis] = b
            how[axis] = "outline only, unvalidated"
        else:
            how[axis] = "no source"

    if "x" not in chosen or "y" not in chosen:
        return None, how

    validated = sum(1 for v in how.values() if v.startswith("cross-validated"))
    confidence = {2: 0.9, 1: 0.6}.get(validated, 0.35)

    return (
        Scale(
            meters_per_pixel_x=chosen["x"].metres_per_pixel,
            meters_per_pixel_y=chosen["y"].metres_per_pixel,
            source="printed_dimension",
            confidence=confidence,
        ),
        how,
    )
