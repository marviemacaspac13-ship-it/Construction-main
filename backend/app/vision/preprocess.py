import cv2
import numpy as np


def preprocess_image(raw_bytes: bytes) -> np.ndarray:
    file_bytes = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image — file may be corrupt or an unsupported format.")
    image = cv2.fastNlMeansDenoisingColored(image, None, h=5, hColor=5, templateWindowSize=7, searchWindowSize=21)

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    image = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    return image


def crop_region(image: np.ndarray, bbox: list[float], pad: int = 12) -> np.ndarray:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, int(x1) - pad)
    y1 = max(0, int(y1) - pad)
    x2 = min(w, int(x2) + pad)
    y2 = min(h, int(y2) + pad)
    return image[y1:y2, x1:x2]
