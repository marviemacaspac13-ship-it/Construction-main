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
    estimate_scope: str | None = Field(None, exclude_if=lambda v: v is None)
    scope_exclusions: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


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
    if source == "detection":
        return [
            "Counts come from symbol matching. The drawing distinguishes symbol "
            "families, not catalog variants, so which variant each count is "
            "priced as follows the Symbol Library mapping rather than the plan.",
        ]
    if source == "tags":
        return [
            "Counts come from reading printed fixture tags. Unlike a dimension "
            "chain, a tag count has nothing to check itself against, so a "
            "fixture the reader missed is invisible and the total is short by "
            "whatever it did not see.",
        ]
    return []


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
    columns_counted: int | None = None,
    manual_column_count: int | None = None,
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
            params.assumption_lines(_families_in(bom), columns_counted, manual_column_count)
            + _source_assumptions(source)
        ),
    )


def estimate_plan(
    plan: PlanSchema,
    catalog: dict[str, dict],
    params: EstimatingParams | None = None,
) -> EstimateResponse:
    """Full path: PlanSchema -> rules -> BOM -> priced estimate."""
    params = params or EstimatingParams()
    if plan.electrical_review is not None:
        # Revalidate Python model_copy/update callers as well as HTTP snapshots.
        plan = PlanSchema.model_validate(plan.model_dump())
        if plan.electrical_review.estimate_scope in ('devices_and_boxes', 'reviewed_device_allowances'):
            review = plan.electrical_review
            with_allowances = review.estimate_scope == 'reviewed_device_allowances'
            bom = [BomLine(item_id=k, quantity=v, rule='electrical_review_v1.device',
                derivation=f'{v} explicitly reviewed physical assemblies; device only', inputs={'assemblies': v})
                for k, v in review.priced_counts().items()]
            bom += [BomLine(item_id=k, quantity=v, rule='electrical_review_v1.compatible_box',
                derivation=f'{v} boxes explicitly selected and confirmed compatible', inputs={'boxes': v})
                for k, v in review.box_counts().items()]
            if with_allowances:
                from app.takeoff.rules.electrical import reviewed_device_allowances
                bom += reviewed_device_allowances(plan, params)
            estimate = estimate_from_bom(bom, catalog, plan.plan_type, params)
            estimate.estimate_scope = review.estimate_scope
            estimate.scope_exclusions = [
                'Breakers, panels, circuit design, and wire/conduit allowances for switches and AC outlets are excluded.'
                if with_allowances else 'Wires, conduit, breakers, panels and circuit design are excluded.']
            estimate.scope_exclusions += [f'Device {i+1} ({c.observation.device_class}): device excluded — {c.exclusion_reason}'
                for i, c in enumerate(review.choices) if c.disposition == 'exclude']
            estimate.scope_exclusions += [f'Device {i+1}: box excluded — {c.box_exclusion_reason}'
                for i, c in enumerate(review.choices) if c.disposition == 'include' and not c.box_item_id]
            if with_allowances:
                estimate.assumptions += [
                    'Reviewed devices and explicitly compatible boxes, with existing wire/conduit allowances '
                    'only for supported ceiling and convenience outlets. These are count-based estimating '
                    'allowances, not measured routes. Switch and AC device counts do not add wiring allowances.',
                ] + estimate.scope_exclusions
            else:
                estimate.assumptions = ['Partial electrical estimate: reviewed devices and explicitly compatible boxes only.'] + estimate.scope_exclusions
            return estimate
    bom = rules_for(plan.plan_type)(plan, params)
    columns_counted = next(
        (c.count for c in plan.concrete if c.kind == "column" and c.counted), None
    )
    estimate = estimate_from_bom(
        bom, catalog, plan.plan_type, params, plan.source, columns_counted, plan.manual_column_count
    )
    if plan.fixture_review is not None:
        tag_assumptions = _source_assumptions('tags')
        estimate.assumptions = [s for s in estimate.assumptions if s not in tag_assumptions] + ([
            'All fixture counts originated as printed fixture tags (WC, LAV, U, FD, CO) read by OCR '
            'and were explicitly reviewed; unlabelled fixtures are counted only where the user added them. '
            'Later source corrections are recorded separately. '
            'Fixture counts imply pipe/fitting allowances, not measured pipe routes.'
        ] if plan.fixture_review.provider == 'tags' else [
            'WC/LAV counts originated as visual proposals and were explicitly reviewed. '
            'Other plumbing tags come from OCR; later source corrections are recorded separately. '
            'Fixture counts imply pipe/fitting allowances, not measured pipe routes.'
        ])
    if plan.electrical_review is not None:
        old = _source_assumptions('detection')
        excluded = sum(c.disposition == 'exclude' for c in plan.electrical_review.choices)
        estimate.assumptions = [s for s in estimate.assumptions if s not in old] + [
            'Electrical source observations were explicitly reviewed. Product choices '
            'and existing library defaults are retained separately from printed labels; '
            'later numeric corrections do not rewrite the original reviewed boxes.',
            f'{excluded} electrical observations were explicitly excluded; their reasons '
            'remain in the electrical review record. No switch or AC allowance was enabled.',
        ]
    return estimate
