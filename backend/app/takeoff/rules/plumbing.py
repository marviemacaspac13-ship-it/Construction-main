"""Plumbing Plan rules.

Fittings are countable. Pipe is sold in fixed 3 m lengths, so run metres
must be converted to whole sticks - that conversion happens at pricing,
which owns the rounding policy; this module reports fractional sticks.
"""

from app.takeoff.bom import BomLine
from app.takeoff.constants import DRAIN_PIPE_ITEM, SUPPLY_PIPE_ITEM
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.common import with_waste
from app.takeoff.schema import PlanSchema
from app.takeoff.units import spec_for

_ITEM_BY_SERVICE = {"supply": SUPPLY_PIPE_ITEM, "drain": DRAIN_PIPE_ITEM}


def compute(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    lines: list[BomLine] = []
    lines += _fittings(plan)
    lines += _pipe_runs(plan, params)
    return lines


def _fittings(plan: PlanSchema) -> list[BomLine]:
    return [
        BomLine(
            item_id=fixture.item_id,
            quantity=float(fixture.count),
            rule="plumbing.fitting_count",
            derivation=f"{fixture.count} counted on plan",
            inputs={"count": float(fixture.count)},
        )
        for fixture in plan.fixtures
        if fixture.count > 0
    ]


def _pipe_runs(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    lines: list[BomLine] = []
    for run in plan.runs:
        item_map = _ITEM_BY_SERVICE.get(run.service)
        if item_map is None:
            continue

        item_id = item_map[run.diameter]
        stick_length = spec_for(item_id).stick_length_m
        if stick_length is None:
            raise ValueError(f"{item_id} has no stick length")

        length_m = with_waste(run.length_m, params.pipe_waste)
        lines.append(
            BomLine(
                item_id=item_id,
                quantity=length_m / stick_length,
                rule="plumbing.pipe_run",
                derivation=(
                    f"run {run.id}: {run.length_m:.2f} m of {run.diameter} {run.service} "
                    f"+ {params.pipe_waste:.0%} waste, / {stick_length} m per length"
                ),
                inputs={"route_length_m": run.length_m},
            )
        )
    return lines
