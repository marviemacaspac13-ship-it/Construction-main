
import cv2
import numpy as np
from app.schemas import Detection
from app.templates_store import load_templates_for_matching

SCALES = [0.6, 0.75, 0.85, 1.0, 1.15, 1.3, 1.5]

MATCH_THRESHOLD = 0.72  
NMS_IOU_THRESHOLD = 0.3 


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
                raw_detections.append(Detection(
                    label=item_id,
                    confidence=score,
                    bbox=[float(x), float(y), float(x + rw), float(y + rh)],
                ))

    return _nms(raw_detections)
