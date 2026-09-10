import os
import numpy as np
from ultralytics import YOLO
from app.schemas import Detection

_model: YOLO | None = None


def _get_model() -> YOLO:
    global _model
    if _model is None:
        weights_path = os.getenv("YOLO_WEIGHTS_PATH", "yolov8n.pt")
        _model = YOLO(weights_path)
    return _model


def detect_materials(image: np.ndarray, confidence_threshold: float = 0.35) -> list[Detection]:
    model = _get_model()
    results = model.predict(image, conf=confidence_threshold, verbose=False)[0]

    detections: list[Detection] = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        label = model.names[cls_id]
        confidence = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        detections.append(Detection(label=label, confidence=confidence, bbox=bbox))

    return detections
