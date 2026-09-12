"""BOM x catalog -> priced estimate.

Owns the rounding policy and the unmatched-item policy. Per
trace-system-requirements.md section 5, an item with no catalog price is
flagged for review and never silently zeroed or dropped, and the price
snapshot time is recorded so historical estimates stay explainable when
prices move.
"""

import math
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.takeoff.bom import BomLine, merge_bom
from app.takeoff.constants import RULES_VERSION
from app.takeoff.params import EstimatingParams
from app.takeoff.rules import rules_for
from app.takeoff.schema import PlanSchema
from app.takeoff.units import DISCRETE_KINDS, UNIT_SPECS


class PricedLine(BaseModel):
    item_id: str
    item_name: str
    unit: str | None
    unit_price: float
    quantity: float
    line_total: float
    rule: str
    derivation: str
    inputs: dict[str, float] = Field(default_factory=dict)


class EstimateResponse(BaseModel):
    plan_type: str
    rules_version: str
    priced_at: str
    line_items: list[PricedLine]
    unpriced: list[BomLine]
    grand_total: float
    assumptions: list[str]


def _families_in(bom: list[BomLine]) -> set[str]:
    """Rule families that actually produced a line.

    A rule is named "<family>.<what>", and merge_bom joins several with a
    "+" when they buy the same SKU, so both separators have to be handled.
    Deriving the families from the BOM rather than from the plan type means
    a new rule brings its own assumption along with it.
    """
    families: set[str] = set()
    for line in bom:
        for rule in line.rule.split("+"):
            family, _, _ = rule.partition(".")
            if family:
                families.add(family)
    return families


def _source_assumptions(source: str) -> list[str]:
    """Caveats that belong to how the plan was read, not to the parameters.

    Symbol matching identifies a symbol FAMILY, never a catalog variant: a
    drawing puts the same circle on a 1-gang and a 3-gang outlet, and the
    same ring on every size of ceiling receptacle. Which SKU a match becomes
    is decided by the folder a reference crop was filed under in the Symbol
    Library, so the variant is a librarian's choice and has to say so - an
    OT01 line otherwise reads as though the plan specified 1-gang.
    """
    if source != "detection":
        return []
    return [
        "Counts come from symbol matching. The drawing distinguishes symbol "
        "families, not catalog variants, so which variant each count is "
        "priced as follows the Symbol Library mapping rather than the plan.",
    ]


def _round_quantity(item_id: str, quantity: float) -> float:
    """Discrete SKUs round up; continuous SKUs keep 2 dp."""
    spec = UNIT_SPECS.get(item_id)
    if spec is not None and spec.kind in DISCRETE_KINDS:
        return float(math.ceil(round(quantity, 6)))
    return round(quantity, 2)


def estimate_from_bom(
    bom: list[BomLine],
    catalog: dict[str, dict],
    plan_type: str,
    params: EstimatingParams,
    source: str = "manual",
) -> EstimateResponse:
    priced: list[PricedLine] = []
    unpriced: list[BomLine] = []
    grand_total = 0.0

    for line in merge_bom(bom):
        row = catalog.get(line.item_id)
        if row is None:
            unpriced.append(line)
            continue

        quantity = _round_quantity(line.item_id, line.quantity)
        unit_price = float(row["price"])
        line_total = round(quantity * unit_price, 2)
        grand_total += line_total

        priced.append(
            PricedLine(
                item_id=line.item_id,
                item_name=row["item_name"],
                unit=row.get("unit"),
                unit_price=unit_price,
                quantity=quantity,
                line_total=line_total,
                rule=line.rule,
                derivation=line.derivation,
                inputs=line.inputs,
            )
        )

    priced.sort(key=lambda li: li.line_total, reverse=True)

    return EstimateResponse(
        plan_type=plan_type,
        rules_version=RULES_VERSION,
        priced_at=datetime.now(timezone.utc).isoformat(),
        line_items=priced,
        unpriced=unpriced,
        grand_total=round(grand_total, 2),
        assumptions=(
            params.assumption_lines(_families_in(bom)) + _source_assumptions(source)
        ),
    )


def estimate_plan(
    plan: PlanSchema,
    catalog: dict[str, dict],
    params: EstimatingParams | None = None,
) -> EstimateResponse:
    """Full path: PlanSchema -> rules -> BOM -> priced estimate."""
    params = params or EstimatingParams()
    bom = rules_for(plan.plan_type)(plan, params)
    return estimate_from_bom(bom, catalog, plan.plan_type, params, plan.source)
