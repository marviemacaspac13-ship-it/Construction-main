"""Registry mapping a plan type to its rule module."""

from typing import Callable

from app.takeoff.bom import BomLine
from app.takeoff.params import EstimatingParams
from app.takeoff.rules import electrical, plumbing, structural
from app.takeoff.schema import PlanSchema

RuleFn = Callable[[PlanSchema, EstimatingParams], list[BomLine]]

RULES_BY_PLAN_TYPE: dict[str, RuleFn] = {
    "Floor Plan": structural.compute,
    "Electrical Plan": electrical.compute,
    "Plumbing Plan": plumbing.compute,
}


def rules_for(plan_type: str) -> RuleFn:
    """Raises KeyError for an unknown plan type - never fall back silently."""
    return RULES_BY_PLAN_TYPE[plan_type]
