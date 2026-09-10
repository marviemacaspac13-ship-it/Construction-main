from collections import defaultdict
from app.schemas import Detection, LineItem, ScanResponse
from app.materials import load_catalog


def price_takeoff(detections: list[Detection]) -> ScanResponse:
    catalog = load_catalog()

    counts: dict[str, int] = defaultdict(int)
    confidences: dict[str, list[float]] = defaultdict(list)
    unmatched: list[Detection] = []

    for det in detections:
        item_id = det.label
        if item_id not in catalog:
            unmatched.append(det)
            continue
        counts[item_id] += 1
        confidences[item_id].append(det.confidence)

    line_items: list[LineItem] = []
    grand_total = 0.0

    for item_id, qty in counts.items():
        row = catalog[item_id]
        unit_price = float(row["price"])
        line_total = unit_price * qty
        grand_total += line_total

        line_items.append(LineItem(
            item_id=item_id,
            item_name=row["item_name"],
            unit=row["unit"],
            unit_price=unit_price,
            quantity=qty,
            line_total=round(line_total, 2),
            avg_confidence=round(sum(confidences[item_id]) / len(confidences[item_id]), 3),
        ))

    line_items.sort(key=lambda li: li.line_total, reverse=True)

    return ScanResponse(
        line_items=line_items,
        unmatched_detections=unmatched,
        grand_total=round(grand_total, 2),
    )
