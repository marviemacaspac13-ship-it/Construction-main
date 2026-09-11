"""Turn OCR text boxes into a validated PlanExtraction.

The spatial logic that matters:

  * Room dimensions sit under their room label, so a label is matched to
    the dimension box directly below it.
  * Margin dimension chains are drawn on lines. Clustering the margin
    numbers by their perpendicular coordinate recovers each line, and a
    line holding a single value that equals the sum of another line IS the
    stated overall for that chain.

That pairing is the checksum, and it also drives cleanup: OCR junk lands
on a dimension line and breaks the sum, so the search allows dropping a
couple of boxes to make a line close. A chain that closes only against its
own sum is NOT validated and is reported as such.
"""

from dataclasses import dataclass
from itertools import combinations

import cv2
import numpy as np

from app.extract.ocr import TextBox, read_array, read_image
from app.extract.to_plan import PlanExtraction, extract_plan
from app.extract.tokens import ROOM_DIM_RE, classify_tag

LABEL_MAX_DY = 70
LABEL_MAX_DX = 120
LINE_TOLERANCE = 16
MIN_SCORE = 0.55
MAX_DROPPED_PER_CHAIN = 2
# How much of a printed overall a chain must already account for before the
# overall is believed to describe the same span. A chain that covers a third
# of some number is probably not a broken reading of it.
MIN_CHAIN_COVERAGE = 0.5

OPPOSITE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}


@dataclass
class Band:
    name: str
    segments: list[float] | None = None
    total: float | None = None
    stated: bool = False  # the total came from an overall printed on the drawing
    closed: bool = False  # ...and the segments actually sum to it


def _has_dims(box: TextBox) -> bool:
    return ROOM_DIM_RE.search(box.text) is not None


def _core_bbox(boxes: list[TextBox]) -> tuple[float, float, float, float]:
    inner = [b for b in boxes if _has_dims(b)]
    if not inner:
        inner = [b for b in boxes if not b.is_number]
    if not inner:
        xs = [b.cx for b in boxes]
        ys = [b.cy for b in boxes]
        return min(xs), min(ys), max(xs), max(ys)
    return (
        min(b.cx for b in inner),
        min(b.cy for b in inner),
        max(b.cx for b in inner),
        max(b.cy for b in inner),
    )


def _assign_band(box: TextBox, core: tuple[float, float, float, float]) -> str | None:
    x1, y1, x2, y2 = core
    distances = {
        "left": x1 - box.cx,
        "right": box.cx - x2,
        "top": y1 - box.cy,
        "bottom": box.cy - y2,
    }
    name, distance = max(distances.items(), key=lambda kv: kv[1])
    return name if distance > 0 else None


def _cluster_lines(boxes: list[TextBox], axis: str) -> list[list[TextBox]]:
    key = (lambda b: b.cy) if axis in ("top", "bottom") else (lambda b: b.cx)
    order = (lambda b: b.cx) if axis in ("top", "bottom") else (lambda b: b.cy)

    lines: list[list[TextBox]] = []
    for box in sorted(boxes, key=key):
        for line in lines:
            if abs(key(box) - key(line[0])) <= LINE_TOLERANCE:
                line.append(box)
                break
        else:
            lines.append([box])
    for line in lines:
        line.sort(key=order)
    return lines


def _match_chain(chain: list[TextBox], total: float) -> list[float] | None:
    """Values from chain that sum to total, dropping up to N outliers.

    Prefers the cleanest fit, not the first one inside tolerance: a junk
    value small enough to hide under the tolerance would otherwise be kept
    and corrupt the segment list even though the total still checks out.
    """
    tolerance = max(2.0, abs(total) * 0.005)
    values = [b.value for b in chain]

    candidates: list[tuple[float, int, list[float]]] = []
    for drop in range(0, MAX_DROPPED_PER_CHAIN + 1):
        if drop >= len(values):
            break
        for removed in combinations(range(len(values)), drop):
            kept = [v for i, v in enumerate(values) if i not in removed]
            if len(kept) < 2:
                continue
            error = abs(sum(kept) - total)
            if error <= tolerance:
                candidates.append((error, -len(kept), kept))

    if not candidates:
        return None
    return min(candidates)[2]


def _overall_above(singles: list[float], chain_sum: float) -> float | None:
    """A printed overall that an incomplete chain plausibly belongs to.

    Takes the closest one above the chain sum, so the unexplained remainder
    is the smallest that fits, and only when the chain already covers most
    of it.
    """
    above = [
        s
        for s in singles
        if s > chain_sum and chain_sum >= s * MIN_CHAIN_COVERAGE
    ]
    return min(above) if above else None


def _resolve_band(name: str, boxes: list[TextBox]) -> Band:
    usable = [b for b in boxes if b.score >= MIN_SCORE and (b.value or 0) > 0]
    lines = _cluster_lines(usable, name)
    band = Band(name=name)

    singles = [line[0].value for line in lines if len(line) == 1]
    chains = [line for line in lines if len(line) >= 2]

    best: tuple[list[float], float] | None = None
    for chain in chains:
        for total in singles:
            matched = _match_chain(chain, total)
            if matched is not None and (best is None or len(matched) > len(best[0])):
                best = (matched, total)

    if best is not None:
        band.segments, band.total = best
        band.stated = band.closed = True
        return band

    longest = max(chains, key=len, default=None)
    if longest is None:
        return band

    band.segments = [b.value for b in longest]
    chain_sum = sum(band.segments)
    band.total = chain_sum

    # The chain did not close on anything. If the edge nonetheless printed an
    # overall, believe the overall: it is one read of one number, while the
    # chain is many reads and a missed segment can only make it too SHORT.
    # The total is corrected and the chain still goes out unclosed, so the
    # checksum reports the gap rather than the gap silently shrinking the
    # building.
    overall = _overall_above(singles, chain_sum)
    if overall is not None:
        band.total = overall
        band.stated = True
    return band


def _rooms(boxes: list[TextBox]) -> list[str]:
    dim_boxes = [b for b in boxes if _has_dims(b)]
    labels = [b for b in boxes if not b.is_number and not _has_dims(b)]

    blocks: list[str] = []
    for dim in dim_boxes:
        candidates = [
            lab
            for lab in labels
            if 0 < dim.cy - lab.cy <= LABEL_MAX_DY and abs(lab.cx - dim.cx) <= LABEL_MAX_DX
        ]
        if candidates:
            label = min(candidates, key=lambda lab: dim.cy - lab.cy)
            blocks.append(f"{label.text} {dim.text}")
        else:
            blocks.append(dim.text)
    return blocks


def extraction_from_boxes(boxes: list[TextBox]) -> PlanExtraction:
    """The spatial pipeline, independent of where the boxes came from."""
    core = _core_bbox(boxes)

    banded: dict[str, list[TextBox]] = {"top": [], "bottom": [], "left": [], "right": []}
    for box in boxes:
        if not box.is_number:
            continue
        band = _assign_band(box, core)
        if band is not None:
            banded[band].append(box)

    bands = {name: _resolve_band(name, group) for name, group in banded.items()}

    # An edge with no printed overall can still be checked against the
    # opposite edge, which measures the same span.
    for name, band in bands.items():
        if band.stated or not band.segments:
            continue
        twin = bands[OPPOSITE[name]]
        if twin.closed and twin.total:
            matched = _match_chain(
                [b for b in banded[name] if b.score >= MIN_SCORE and (b.value or 0) > 0],
                twin.total,
            )
            if matched is not None:
                band.segments, band.total = matched, twin.total
                band.stated = band.closed = True

    chains = [
        (band.segments, band.total)
        for band in bands.values()
        if band.stated and band.segments and band.total
    ]

    width = next((bands[n].total for n in ("top", "bottom") if bands[n].total), 0.0)
    length = next((bands[n].total for n in ("left", "right") if bands[n].total), 0.0)

    tags = [b.text for b in boxes if classify_tag(b.text) is not None]
    return extract_plan(width, length, _rooms(boxes), chains, tags)


def read_plan(path: str) -> PlanExtraction:
    """Full path: image file -> validated, metric extraction."""
    return extraction_from_boxes(read_image(path))


def read_plan_array(image) -> PlanExtraction:
    """Same, for an image already decoded in memory (an HTTP upload)."""
    return extraction_from_boxes(read_array(image))


def read_plan_bytes(raw: bytes) -> PlanExtraction:
    """Same, straight from an uploaded file's bytes."""
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("could not decode image - corrupt or unsupported format")
    return read_plan_array(image)
