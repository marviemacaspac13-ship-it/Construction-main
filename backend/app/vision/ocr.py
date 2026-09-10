import os
import re
import numpy as np
import pytesseract

from app.schemas import Detection
from app.vision.preprocess import crop_region

if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
_DIMENSION_PATTERN = re.compile(
    r'(\d+/\d+\s*["\u2033]?|\d+(\.\d+)?\s*(mm|MM|A|AWG)|#\s?\d+)',
)


def extract_dimension_text(image: np.ndarray, detections: list[Detection]) -> list[Detection]:
    for det in detections:
        patch = crop_region(image, det.bbox, pad=20)
        if patch.size == 0:
            continue

        text = pytesseract.image_to_string(patch, config="--psm 7")
        match = _DIMENSION_PATTERN.search(text)
        if match:
            det.dimension_text = match.group(0).strip()

    return detections
