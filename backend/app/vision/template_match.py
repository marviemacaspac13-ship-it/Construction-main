
import cv2
import numpy as np
from app.schemas import Detection
from app.templates_store import load_templates_for_matching

SCALES = [0.6, 0.75, 0.85, 1.0, 1.15, 1.3, 1.5]

# Set from a hand count. On `05.png` the true figures are 21 ceiling outlets
# and 14 convenience outlets as first counted; this threshold recovered 15
# and 13 of them, against 13 and 8 at the old 0.72.
#
# 0.66 is the last safe step, not a comfortable middle. One notch lower at
# 0.64 the wall outlet jumps to 28 against a true 14, and by 0.55 the sheet
# yields 145 - door swings and wall hatching. Do not lower it without new
# ground truth.
#
# The outlet count has since been redone (25 Sep): 05.png carries 18 wall
# outlets, and 2 of the 13 above were a door jamb and a wall line, so
# sitting under the hand count did NOT prove every hit was real. Only a
# per-hit check against the drawing can. With the duplex crops that now
# stand in for the originals the sheet reads 16 of 18 with none false;
# `tests/test_ground_truth.py` has the three counted plans.
#
# Recall bought here is paid for elsewhere: at 0.66 plans that used to match
# nothing return two to five stray hits. MIN_DEVICES in `main.py` is what
# keeps those from being priced - the two constants move together.
MATCH_THRESHOLD = 0.66
NMS_IOU_THRESHOLD = 0.3

# Every symbol in the library is drawn on a CIRCLE, and at 0.66 the matcher
# also scores bare crossings of two thin lines - dimension lines, grid lines
# - because a "+" is most of a crossed-circle template. Checked hit by hit
# on 27 Sep 2026: all 4 "lights" on the power-only 10.png and 10 of the 17
# on 08.png were line crossings or text, not symbols. The recorded "08.png
# finds 19 of 19" had matched the hand count in total only.
#
# So a hit must have a ring round its centre: walk outward along 48
# directions, skipping those near the four arms, and count how many meet
# ink between 0.2 and 0.5 of the box size. Measured on the three
# hand-counted sheets: real symbols 0.79-1.00, line crossings 0.00-0.11,
# a text corner 0.61. The library's own crops score 0.75-0.96, and
# `tests/test_ring_check.py` fails if a new one does not pass - a symbol
# that is not a circle needs this check rethought, not lowered.
RING_MIN = 0.70
RING_RADII = (0.2, 0.5)
RING_DIRECTIONS = 48
RING_SKIP_DEG = 20
INK = 128


def _ring_directions() -> np.ndarray:
    angles = np.arange(RING_DIRECTIONS) * (360.0 / RING_DIRECTIONS)
    off_axis = np.min(
        [np.abs((angles - q + 180) % 360 - 180) for q in (0, 90, 180, 270)], axis=0
    )
    return np.radians(angles[off_axis >= RING_SKIP_DEG])


_DIRECTIONS = _ring_directions()


def ring_score(gray: np.ndarray, bbox: list[float]) -> float:
    """Fraction of off-axis directions that meet ink at a ring's radius."""
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    size = min(x2 - x1, y2 - y1)
    radii = np.arange(RING_RADII[0] * size, RING_RADII[1] * size, 0.5)
    xs = np.rint(cx + np.outer(np.cos(_DIRECTIONS), radii)).astype(int)
    ys = np.rint(cy + np.outer(np.sin(_DIRECTIONS), radii)).astype(int)
    h, w = gray.shape[:2]
    inside = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    ink = np.zeros(xs.shape, dtype=bool)
    ink[inside] = gray[ys[inside], xs[inside]] < INK
    return float(ink.any(axis=1).mean())


def _iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / (area_a + area_b - inter)


def _nms(detections: list[Detection]) -> list[Detection]:
    kept: list[Detection] = []
    by_item: dict[str, list[Detection]] = {}
    for d in detections:
        by_item.setdefault(d.label, []).append(d)

    for item_dets in by_item.values():
        item_dets.sort(key=lambda d: d.confidence, reverse=True)
        chosen: list[Detection] = []
        for d in item_dets:
            if all(_iou(d.bbox, c.bbox) < NMS_IOU_THRESHOLD for c in chosen):
                chosen.append(d)
        kept.extend(chosen)

    return kept


def match_templates(image_bgr: np.ndarray) -> list[Detection]:
    templates = load_templates_for_matching()
    if not templates:
        return []

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape[:2]

    raw_detections: list[Detection] = []

    for item_id, template in templates:
        th, tw = template.shape[:2]
        for scale in SCALES:
            rw, rh = int(tw * scale), int(th * scale)
            if rw < 8 or rh < 8 or rw > img_w or rh > img_h:
                continue

            resized = cv2.resize(template, (rw, rh))
            result = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(result >= MATCH_THRESHOLD)

            for x, y in zip(xs, ys):
                score = float(result[y, x])
                bbox = [float(x), float(y), float(x + rw), float(y + rh)]
                # Before NMS, not after: a crossing that out-scores a real
                # symbol beside it would otherwise suppress it.
                if ring_score(gray, bbox) < RING_MIN:
                    continue
                raw_detections.append(Detection(
                    label=item_id,
                    confidence=score,
                    bbox=bbox,
                ))

    return _nms(raw_detections)
