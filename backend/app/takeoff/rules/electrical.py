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
    lines += _wire_and_conduit_from_devices(plan, params)
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


# Gauge follows what the device is for, using the same split the measured
# path uses: lighting circuits take #14, convenience circuits #12.
_GAUGE_BY_KIND = {
    "lighting": WIRE_ITEM_BY_SERVICE["lighting"],
    "convenience": WIRE_ITEM_BY_SERVICE["convenience"],
}


def _wire_and_conduit_from_devices(
    plan: PlanSchema, params: EstimatingParams
) -> list[BomLine]:
    """Wire and conduit derived from the device count, when no route is known.

    Wire is roughly two thirds of an electrical estimate and no drawing
    states its length - a plan shows where the outlets are, never how much
    cable reaches them. Without this the trade prices at a small fraction
    of itself: 05.png came to P1,224 against a realistic P18,000-25,000.

    **Only fires when `plan.runs` is empty.** A measured route always wins,
    and the two must never both apply. The rule names differ from the
    measured ones for the same reason: the audit ledger records rule names,
    and a reader has to be able to tell a measured length from a derived
    one.
    """
    if plan.runs:
        return []

    lighting = sum(f.count for f in plan.fixtures if f.item_id in CEILING_OUTLET_ITEMS)
    convenience = sum(f.count for f in plan.fixtures if f.item_id in WIRING_DEVICE_ITEMS)
    devices = lighting + convenience
    if devices <= 0:
        return []

    # A lighting point and a convenience outlet take different allowances:
    # a light hangs off a ceiling run with no wall drop (see params.py).
    per_point = {
        "lighting": (params.lighting_wire_m_per_point, params.lighting_route_m_per_point),
        "convenience": (params.wire_m_per_device, params.conduit_m_per_device),
    }

    lines: list[BomLine] = []
    for kind, count in (("lighting", lighting), ("convenience", convenience)):
        wire_each = per_point[kind][0]
        if count <= 0 or wire_each <= 0:
            continue
        lines.append(
            BomLine(
                item_id=_GAUGE_BY_KIND[kind],
                quantity=with_waste(count * wire_each, params.wire_waste),
                rule="electrical.conductor_from_count",
                derivation=(
                    f"{count} {kind} devices x {wire_each:g} m of conductor "
                    f"each + {params.wire_waste:.0%} waste - DERIVED from the count, no "
                    f"circuit routes were measured"
                ),
                inputs={"devices": float(count)},
            )
        )

    parts = [
        (kind, count, per_point[kind][1])
        for kind, count in (("lighting", lighting), ("convenience", convenience))
        if count > 0 and per_point[kind][1] > 0
    ]
    if parts:
        conduit_m = sum(count * each for _, count, each in parts)
        lines.append(
            BomLine(
                item_id=CONDUIT_ITEM,
                quantity=with_waste(conduit_m, params.conduit_waste),
                rule="electrical.conduit_from_count",
                derivation=(
                    " + ".join(f"{count} {kind} x {each:g} m" for kind, count, each in parts)
                    + f" of conduit + {params.conduit_waste:.0%} waste - DERIVED from the "
                    f"count, no circuit routes were measured"
                ),
                inputs={"devices": float(sum(count for _, count, _ in parts))},
            )
        )
    return lines
