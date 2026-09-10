from pydantic import BaseModel
from typing import List, Optional


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: List[float]
    dimension_text: Optional[str] = None


class LineItem(BaseModel):
    item_id: str
    item_name: str
    unit: Optional[str]
    unit_price: float
    quantity: int
    line_total: float
    avg_confidence: float


class ScanResponse(BaseModel):
    line_items: List[LineItem]
    unmatched_detections: List[Detection]
    grand_total: float
