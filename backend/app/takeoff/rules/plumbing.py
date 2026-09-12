"""Plumbing Plan rules.

Fittings are countable. Pipe is sold in fixed 3 m lengths, so run metres
must be converted to whole sticks - that conversion happens at pricing,
which owns the rounding policy; this module reports fractional sticks.
"""

from app.takeoff.bom import BomLine
from app.takeoff.constants import DRAIN_PIPE_ITEM, FIXTURE_PLUMBING, SUPPLY_PIPE_ITEM
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.common import with_waste
from app.takeoff.schema import PlanSchema
from app.takeoff.units import spec_for

_ITEM_BY_SERVICE = {"supply": SUPPLY_PIPE_ITEM, "drain": DRAIN_PIPE_ITEM}


def compute(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    lines: list[BomLine] = []
    lines += _fittings(plan)
    lines += _pipe_runs(plan, params)
    lines += _from_fixture_tags(plan, params)
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


def _pipe_line(
    item_id: str, length_m: float, rule: str, derivation: str, params: EstimatingParams
) -> BomLine:
    """Metres of pipe as fractional 3 m sticks; pricing owns the rounding."""
    stick_length = spec_for(item_id).stick_length_m
    if stick_length is None:  # pragma: no cover - guarded by the units table
        raise ValueError(f"{item_id} has no stick length")

    with_slack = with_waste(length_m, params.pipe_waste)
    return BomLine(
        item_id=item_id,
        quantity=with_slack / stick_length,
        rule=rule,
        derivation=(
            f"{derivation} = {length_m:.2f} m + {params.pipe_waste:.0%} waste, "
            f"/ {stick_length} m per length"
        ),
        inputs={"route_length_m": round(length_m, 4)},
    )


def _from_fixture_tags(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    """Pipe and fittings implied by the fixtures counted on the plan.

    The fixtures themselves are never priced - a toilet is client-supplied,
    the same way a floor plan prices walls and not the doors in them. What
    they earn is the pipe and fittings that serve them, one branch and one
    fitting each.

    This is the plumbing counterpart of a detected outlet implying a
    utility box: the count comes off the drawing, the materials come from
    the rules.
    """
    lines: list[BomLine] = []

    for tag, count in sorted(plan.fixture_tags.items()):
        if count <= 0:
            continue
        parts = FIXTURE_PLUMBING.get(tag)
        if not parts:  # a cleanout adds no pipe, and nothing else is known
            continue

        label = tag.replace("_", " ")
        for service, length_m in (
            ("drain", params.drain_branch_m_per_fixture),
            ("supply", params.supply_branch_m_per_fixture),
        ):
            pipe = parts.get(service)
            if pipe is None or length_m <= 0:
                continue
            lines.append(
                _pipe_line(
                    pipe,
                    count * length_m,
                    f"plumbing.fixture_{service}",
                    f"{count} x {label} at {length_m:g} m of {service} branch each",
                    params,
                )
            )

            fitting = parts.get(f"{service}_fitting")
            if fitting is not None:
                lines.append(
                    BomLine(
                        item_id=fitting,
                        quantity=float(count),
                        rule=f"plumbing.fixture_{service}_fitting",
                        derivation=f"1 {service} branch fitting per {label} x {count}",
                        inputs={"fixtures": float(count)},
                    )
                )

    return lines
