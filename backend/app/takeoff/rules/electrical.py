"""Electrical Plan rules.

Devices are genuinely countable, so symbol detection maps to them 1:1.
Wire and conduit are not - they need route lengths.
"""

from app.takeoff.bom import BomLine
from app.takeoff.constants import (
    CEILING_OUTLET_ITEMS,
    CONDUIT_ITEM,
    JUNCTION_BOX_ITEM,
    UTILITY_BOX_ITEM,
    WIRE_ITEM_BY_SERVICE,
    WIRING_DEVICE_ITEMS,
)
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.common import with_waste
from app.takeoff.schema import PlanSchema


def compute(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    lines: list[BomLine] = []
    lines += _devices(plan)
    lines += _boxes(plan)
    lines += _wire_and_conduit(plan, params)
    return lines


def _devices(plan: PlanSchema) -> list[BomLine]:
    return [
        BomLine(
            item_id=fixture.item_id,
            quantity=float(fixture.count),
            rule="electrical.device_count",
            derivation=f"{fixture.count} counted on plan",
            inputs={"count": float(fixture.count)},
        )
        for fixture in plan.fixtures
        if fixture.count > 0
    ]


def _boxes(plan: PlanSchema) -> list[BomLine]:
    devices = sum(f.count for f in plan.fixtures if f.item_id in WIRING_DEVICE_ITEMS)
    ceiling = sum(f.count for f in plan.fixtures if f.item_id in CEILING_OUTLET_ITEMS)

    lines: list[BomLine] = []
    if devices > 0:
        lines.append(
            BomLine(
                item_id=UTILITY_BOX_ITEM,
                quantity=float(devices),
                rule="electrical.utility_boxes",
                derivation=f"1 utility box per wiring device x {devices} devices",
                inputs={"wiring_devices": float(devices)},
            )
        )
    if ceiling > 0:
        lines.append(
            BomLine(
                item_id=JUNCTION_BOX_ITEM,
                quantity=float(ceiling),
                rule="electrical.junction_boxes",
                derivation=f"1 junction box per ceiling outlet x {ceiling} outlets",
                inputs={"ceiling_outlets": float(ceiling)},
            )
        )
    return lines


def _wire_and_conduit(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    lines: list[BomLine] = []
    for run in plan.runs:
        wire_item = WIRE_ITEM_BY_SERVICE.get(run.service)
        if wire_item is None:  # a plumbing run on an electrical plan
            continue

        slack_m = run.terminations * params.slack_per_termination_m
        wire_m = with_waste((run.length_m + slack_m) * run.conductors, params.wire_waste)
        conduit_m = with_waste(run.length_m, params.conduit_waste)

        lines.append(
            BomLine(
                item_id=wire_item,
                quantity=wire_m,
                rule="electrical.conductor",
                derivation=(
                    f"run {run.id}: ({run.length_m:.2f} m + {slack_m:.2f} m slack) "
                    f"x {run.conductors} conductors + {params.wire_waste:.0%} waste "
                    f"[{run.service}]"
                ),
                inputs={"route_length_m": run.length_m},
            )
        )
        lines.append(
            BomLine(
                item_id=CONDUIT_ITEM,
                quantity=conduit_m,
                rule="electrical.conduit",
                derivation=(
                    f"run {run.id}: {run.length_m:.2f} m route "
                    f"+ {params.conduit_waste:.0%} waste"
                ),
                inputs={"route_length_m": run.length_m},
            )
        )
    return lines
