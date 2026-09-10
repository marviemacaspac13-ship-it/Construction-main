"""Floor Plan rules: masonry, mortar, concrete, reinforcement.

None of these quantities come from counting symbols. They are derived from
wall geometry and poured volumes.
"""

from collections import defaultdict

from app.takeoff.bom import BomLine
from app.takeoff.constants import (
    CEMENT_ITEM,
    CHB_ITEM,
    CHB_MORTAR_PER_M2,
    CHB_PER_M2,
    CONCRETE_MIX_PER_M3,
    GRAVEL_ITEM,
    SAND_ITEM,
    TIE_WIRE_ITEM,
)
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.common import bars_across, rebar_mass_kg, with_waste
from app.takeoff.schema import PlanSchema
from app.takeoff.units import spec_for


def compute(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    lines: list[BomLine] = []
    lines += _masonry_and_mortar(plan, params)
    lines += _concrete(plan, params)
    lines += _reinforcement(plan, params)
    return lines


def _masonry_and_mortar(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    area_by_thickness: dict[str, float] = defaultdict(float)
    for wall in plan.walls:
        area_by_thickness[wall.thickness] += wall.net_area_m2(params.default_wall_height_m)

    lines: list[BomLine] = []
    for thickness, area in sorted(area_by_thickness.items()):
        if area <= 0:
            continue

        blocks = with_waste(area * CHB_PER_M2, params.chb_waste)
        lines.append(
            BomLine(
                item_id=CHB_ITEM[thickness],
                quantity=blocks,
                rule="structural.chb_blocks",
                derivation=(
                    f"{area:.2f} m^2 net {thickness} wall x {CHB_PER_M2} pcs/m^2 "
                    f"+ {params.chb_waste:.0%} waste"
                ),
                inputs={"wall_area_m2": round(area, 4)},
            )
        )

        mortar = CHB_MORTAR_PER_M2[thickness]
        lines.append(
            BomLine(
                item_id=CEMENT_ITEM,
                quantity=with_waste(area * mortar["cement_bags"], params.mortar_waste),
                rule="structural.laying_mortar",
                derivation=(
                    f"{area:.2f} m^2 {thickness} wall x {mortar['cement_bags']} bags/m^2 "
                    f"laying mortar + {params.mortar_waste:.0%} waste"
                ),
                inputs={"wall_area_m2": round(area, 4)},
            )
        )
        lines.append(
            BomLine(
                item_id=SAND_ITEM,
                quantity=with_waste(area * mortar["sand_m3"], params.mortar_waste),
                rule="structural.laying_mortar",
                derivation=(
                    f"{area:.2f} m^2 {thickness} wall x {mortar['sand_m3']} m^3/m^2 "
                    f"laying mortar + {params.mortar_waste:.0%} waste"
                ),
                inputs={"wall_area_m2": round(area, 4)},
            )
        )
    return lines


def _concrete(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    volume_by_class: dict[str, float] = defaultdict(float)
    for element in plan.concrete:
        volume_by_class[element.mix_class] += element.volume_m3

    lines: list[BomLine] = []
    for mix_class, volume in sorted(volume_by_class.items()):
        mix = CONCRETE_MIX_PER_M3[mix_class]
        for item_id, key, unit in (
            (CEMENT_ITEM, "cement_bags", "bags/m^3"),
            (SAND_ITEM, "sand_m3", "m^3/m^3"),
            (GRAVEL_ITEM, "gravel_m3", "m^3/m^3"),
        ):
            lines.append(
                BomLine(
                    item_id=item_id,
                    quantity=with_waste(volume * mix[key], params.concrete_waste),
                    rule="structural.concrete",
                    derivation=(
                        f"{volume:.2f} m^3 Class {mix_class} concrete x {mix[key]} {unit} "
                        f"+ {params.concrete_waste:.0%} waste"
                    ),
                    inputs={"concrete_volume_m3": round(volume, 4)},
                )
            )
    return lines


def _reinforcement(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    total_length_m = 0.0
    for wall in plan.walls:
        height = wall.effective_height_m(params.default_wall_height_m)
        vertical = bars_across(wall.length_m, params.vertical_bar_spacing_m) * height
        horizontal = bars_across(height, params.horizontal_bar_spacing_m) * wall.length_m
        total_length_m += vertical + horizontal

    if total_length_m <= 0:
        return []

    bar = params.rebar_item_id
    length_with_waste = with_waste(total_length_m, params.rebar_waste)
    stick_length = spec_for(bar).stick_length_m
    if stick_length is None:  # pragma: no cover - guarded by the units table
        raise ValueError(f"{bar} has no stick length; it cannot be used as rebar")

    mass_kg = rebar_mass_kg(bar, length_with_waste)
    tie_wire_kg = mass_kg * params.tie_wire_kg_per_100kg_rebar / 100.0

    return [
        BomLine(
            item_id=bar,
            quantity=length_with_waste / stick_length,
            rule="structural.rebar",
            derivation=(
                f"{total_length_m:.2f} m of {bar} at "
                f"{params.vertical_bar_spacing_m} m o.c. vertical / "
                f"{params.horizontal_bar_spacing_m} m o.c. horizontal "
                f"+ {params.rebar_waste:.0%} waste, / {stick_length} m per length"
            ),
            inputs={"rebar_length_m": round(total_length_m, 4)},
        ),
        BomLine(
            item_id=TIE_WIRE_ITEM,
            quantity=tie_wire_kg,
            rule="structural.tie_wire",
            derivation=(
                f"{mass_kg:.2f} kg of {bar} x "
                f"{params.tie_wire_kg_per_100kg_rebar} kg tie wire per 100 kg"
            ),
            inputs={"rebar_mass_kg": round(mass_kg, 4)},
        ),
    ]
