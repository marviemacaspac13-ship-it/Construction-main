"""Adapter: symbol detections -> PlanSchema.

Fills in only what detection can honestly supply - counts of discrete
symbols. Wall geometry and run lengths cannot be detected, so they stay
empty here and come from the OCR path or from user input.

This is the join between the two estimating paths: both produce a
PlanSchema, and the same rule engine prices whatever is in it.
"""

from collections import Counter

from app.schemas import Detection
from app.takeoff.schema import FixtureCount, PlanSchema, PlanType
from app.takeoff.units import UNIT_SPECS


def plan_from_detections(
    detections: list[Detection], plan_type: PlanType
) -> PlanSchema:
    """Count detected symbols into fixtures the rule engine can price.

    A detection label IS a catalog item_id, because templates are stored in
    a folder named after the item. Labels with no catalog entry are dropped
    rather than guessed at; use `unknown_labels` to report them.
    """
    counts = Counter(det.label for det in detections if det.label in UNIT_SPECS)
    return PlanSchema(
        plan_type=plan_type,
        source="detection",
        fixtures=[
            FixtureCount(item_id=item_id, count=count)
            for item_id, count in sorted(counts.items())
        ],
    )


def unknown_labels(detections: list[Detection]) -> list[str]:
    """Detected labels that match no catalog SKU, so an operator can review."""
    return sorted({det.label for det in detections if det.label not in UNIT_SPECS})