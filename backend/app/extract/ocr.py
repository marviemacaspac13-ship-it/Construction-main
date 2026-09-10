"""Getting text off a plan image.

Two passes are required, not one. Margin dimension chains on the left and
right edges are printed rotated 90 degrees, and a single upright pass
misses them almost entirely - on the 4-bedroom sample it recovered the top
and bottom chains but only one value from each side. Running the image
again rotated, then mapping the boxes back, recovers them.

Engine is RapidOCR (PP-OCR models on ONNX Runtime): pip-installable with
no system binary, and better on small rotated plan text than Tesseract
(trace-system-requirements.md section 3).
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

# OCR frequently mangles the 'x' between room dimensions into a glyph it
# cannot name. Anything that is not a digit, letter, space, dot or comma
# sitting between two digits is that separator.
_SEP_FIX_RE = re.compile(r"(\d)\s*[^\dA-Za-z\s.,]+\s*(\d)")

# A real 'x' may or may not be read with spaces around it. Both spellings
# must canonicalise to one string, or the upright and rotated passes
# produce "3700 x 3500" and "3700x3500" and the room is counted twice.
_X_SEP_RE = re.compile(r"(\d)\s*[xX\u00d7]\s*(\d)")


def normalize_text(text: str) -> str:
    """Repair the dimension separator, canonicalise it, collapse whitespace."""
    fixed = _SEP_FIX_RE.sub(r"\1x\2", text)
    fixed = _X_SEP_RE.sub(r"\1x\2", fixed)
    return " ".join(fixed.split())


@dataclass(frozen=True)
class TextBox:
    text: str
    cx: float
    cy: float
    score: float
    rotated: bool  # True if it came from the rotated pass

    @property
    def is_number(self) -> bool:
        return bool(re.fullmatch(r"\d+(?:\.\d+)?", self.text))

    @property
    def value(self) -> float | None:
        return float(self.text) if self.is_number else None


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _boxes_from(result, height: int, rotated: bool) -> list[TextBox]:
    boxes: list[TextBox] = []
    for quad, text, score in result or []:
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        cx, cy = sum(xs) / 4.0, sum(ys) / 4.0
        if rotated:
            # image was rotated 90 clockwise: original x = cy, y = H-1-cx
            cx, cy = cy, height - 1 - cx
        cleaned = normalize_text(text)
        if cleaned:
            boxes.append(TextBox(cleaned, cx, cy, float(score), rotated))
    return boxes


DEDUPE_RADIUS = 25.0


def _dedupe(boxes: list[TextBox]) -> list[TextBox]:
    """Drop the same string read twice at the same place by both passes.

    Distance-based rather than grid-rounded: the two passes place the same
    box a few pixels apart, and a grid boundary between them would keep
    both, duplicating a room.
    """
    kept: list[TextBox] = []
    for box in sorted(boxes, key=lambda b: -b.score):
        duplicate = next(
            (
                k
                for k in kept
                if k.text == box.text
                and abs(k.cx - box.cx) <= DEDUPE_RADIUS
                and abs(k.cy - box.cy) <= DEDUPE_RADIUS
            ),
            None,
        )
        if duplicate is None:
            kept.append(box)
    return sorted(kept, key=lambda b: (b.cy, b.cx))


def read_image(path: str | Path) -> list[TextBox]:
    """Every text box on the plan, upright and rotated passes merged."""
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"could not read image: {path}")
    return read_array(image)


def read_array(image: np.ndarray) -> list[TextBox]:
    engine = _engine()
    height = image.shape[0]

    upright, _ = engine(image)
    boxes = _boxes_from(upright, height, rotated=False)

    rotated_img = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    rotated, _ = engine(rotated_img)
    boxes += _boxes_from(rotated, height, rotated=True)

    return _dedupe(boxes)
