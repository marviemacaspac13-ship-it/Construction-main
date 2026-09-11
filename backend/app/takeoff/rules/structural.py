"""Floor Plan rules: masonry, mortar, concrete, reinforcement.

None of these quantities come from counting symbols. They are derived from
wall geometry and poured volumes.
"""

import math
from collections import defaultdict

from app.takeoff.bom import BomLine
from app.takeoff.constants import (
    BEAM_MAIN_BARS,
    BEAM_STIRRUP_REST_SPACING_M,
    BEAM_STIRRUP_ZONES,
    CEMENT_ITEM,
    CHB_ITEM,
    CHB_MORTAR_PER_M2,
    CHB_PER_M2,
    CONCRETE_COVER_M,
    CONCRETE_MIX_PER_M3,
    COLUMN_TIES_PER_COLUMN,
    FOOTING_BARS_EACH_WAY,
    GRAVEL_ITEM,
    MAIN_BAR_ITEM,
    SAND_ITEM,
    SLAB_MESH_M_PER_M2,
    TIE_BAR_ITEM,
    TIE_WIRE_ITEM,
)
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.common import bars_across, rebar_mass_kg, with_waste
from app.takeoff.schema import ConcreteElement, PlanSchema
from app.takeoff.units import spec_for


def compute(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    lines: list[BomLine] = []
    lines += _masonry_and_mortar(plan, params)
    lines += _concrete(plan, params)
    lines += _reinforcement(plan, params)
    lines += _frame_reinforcement(plan, params)
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


def _bar_lines(
    item_id: str, length_m: float, rule: str, derivation: str, params: EstimatingParams
) -> list[BomLine]:
    """One bar purchase plus the tie wire that goes with it.

    Bars are bought by the 6 m length, so the quantity is metres over stick
    length. merge_bom folds these into whatever else buys the same SKU -
    slab mesh and CHB wall bars are both DB01 and must appear as one line.
    """
    if length_m <= 0:
        return []

    stick_length = spec_for(item_id).stick_length_m
    if stick_length is None:
        raise ValueError(f"{item_id} has no stick length; it cannot be used as rebar")

    with_slack = with_waste(length_m, params.rebar_waste)
    mass_kg = rebar_mass_kg(item_id, with_slack)
    return [
        BomLine(
            item_id=item_id,
            quantity=with_slack / stick_length,
            rule=rule,
            derivation=(
                f"{derivation} = {length_m:.2f} m of {item_id} "
                f"+ {params.rebar_waste:.0%} waste, / {stick_length} m per length"
            ),
            inputs={"rebar_length_m": round(length_m, 4)},
        ),
        BomLine(
            item_id=TIE_WIRE_ITEM,
            quantity=mass_kg * params.tie_wire_kg_per_100kg_rebar / 100.0,
            rule="structural.tie_wire",
            derivation=(
                f"{mass_kg:.2f} kg of {item_id} x "
                f"{params.tie_wire_kg_per_100kg_rebar} kg tie wire per 100 kg"
            ),
            inputs={"rebar_mass_kg": round(mass_kg, 4)},
        ),
    ]


def _tie_loop_m(width_m: float, depth_m: float, cover_m: float) -> float:
    """Perimeter of a closed tie just inside the cover on all four faces."""
    w = width_m - 2 * cover_m
    d = depth_m - 2 * cover_m
    return 2 * (w + d) if w > 0 and d > 0 else 0.0


def _column_steel(el: ConcreteElement, params: EstimatingParams) -> list[BomLine]:
    """Guide: 4 x 16mm verticals and 24 x 10mm ties per standard column."""
    lines: list[BomLine] = []

    verticals_m = el.count * BEAM_MAIN_BARS * el.height_m
    lines += _bar_lines(
        MAIN_BAR_ITEM,
        verticals_m,
        "structural.column_bars",
        f"{el.count} columns x {BEAM_MAIN_BARS} verticals x {el.height_m:g} m",
        params,
    )

    loop_m = _tie_loop_m(el.width_m, el.length_m, CONCRETE_COVER_M["column"])
    if loop_m > 0:
        lines += _bar_lines(
            TIE_BAR_ITEM,
            el.count * COLUMN_TIES_PER_COLUMN * loop_m,
            "structural.column_ties",
            (
                f"{el.count} columns x {COLUMN_TIES_PER_COLUMN} ties x {loop_m:.2f} m "
                f"per loop ({el.width_m:g} x {el.length_m:g} m less "
                f"{CONCRETE_COVER_M['column']:g} m cover)"
            ),
            params,
        )
    return lines


def beam_stirrup_count(length_m: float) -> int:
    """Stirrups on one beam, by the guide zoned schedule.

    0.50 m at 50 mm, 0.50 m at 100 mm, 1.00 m at 150 mm, the rest at
    200 mm, each zone counting its spacings plus one. On the guide worked
    5 m beam this is 11 + 6 + 8 + 16 = 41.

    Zones are laid once over the beam rather than once per end, which is
    what the guide computes. A beam shorter than the zones gets only the
    zones that fit.
    """
    if length_m <= 0:
        return 0

    count = 0
    remaining = length_m
    for zone_m, spacing_m in BEAM_STIRRUP_ZONES:
        if remaining <= 0:
            break
        span = min(zone_m, remaining)
        count += math.ceil(span / spacing_m) + 1
        remaining -= span
    if remaining > 0:
        count += math.ceil(remaining / BEAM_STIRRUP_REST_SPACING_M) + 1
    return count


def _beam_steel(el: ConcreteElement, params: EstimatingParams) -> list[BomLine]:
    """Guide: 4 x 16mm mains (2 top, 2 bottom) and zoned 10mm stirrups."""
    lines: list[BomLine] = []
    length_m = el.length_m

    lines += _bar_lines(
        MAIN_BAR_ITEM,
        el.count * BEAM_MAIN_BARS * length_m,
        "structural.beam_bars",
        f"{BEAM_MAIN_BARS} main bars x {length_m:.2f} m (2 top, 2 bottom)",
        params,
    )

    # A beam is drawn width x depth; height_m carries the depth here.
    loop_m = _tie_loop_m(el.width_m, el.height_m, CONCRETE_COVER_M["beam"])
    stirrups = beam_stirrup_count(length_m)
    if loop_m > 0 and stirrups > 0:
        lines += _bar_lines(
            TIE_BAR_ITEM,
            el.count * stirrups * loop_m,
            "structural.beam_stirrups",
            (
                f"{stirrups} stirrups over {length_m:.2f} m "
                f"(50/100/150 mm zones then {BEAM_STIRRUP_REST_SPACING_M:g} m) "
                f"x {loop_m:.2f} m per loop"
            ),
            params,
        )
    return lines


def _footing_steel(el: ConcreteElement, params: EstimatingParams) -> list[BomLine]:
    """Guide: 6 + 6 16mm bars, cut to the footing side less cover both ends."""
    cover = CONCRETE_COVER_M["footing"]
    cut_w = el.width_m - 2 * cover
    cut_l = el.length_m - 2 * cover
    if cut_w <= 0 or cut_l <= 0:
        return []

    per_footing = FOOTING_BARS_EACH_WAY * (cut_w + cut_l)
    return _bar_lines(
        MAIN_BAR_ITEM,
        el.count * per_footing,
        "structural.footing_bars",
        (
            f"{el.count} footings x {FOOTING_BARS_EACH_WAY} bars each way, "
            f"cut {cut_w:.2f} m and {cut_l:.2f} m "
            f"({el.width_m:g} m square less {cover:g} m cover) = "
            f"{per_footing:.2f} m each"
        ),
        params,
    )


def _slab_steel(el: ConcreteElement, params: EstimatingParams) -> list[BomLine]:
    """Guide: a flat rate per m2 of slab rather than a bar spacing."""
    area_m2 = el.count * el.width_m * el.length_m
    return _bar_lines(
        TIE_BAR_ITEM,
        area_m2 * SLAB_MESH_M_PER_M2,
        "structural.slab_mesh",
        f"{area_m2:.2f} m^2 of slab x {SLAB_MESH_M_PER_M2:g} m/m^2 mesh",
        params,
    )


_STEEL_BY_KIND = {
    "column": _column_steel,
    "footing": _footing_steel,
    "beam": _beam_steel,
    "slab": _slab_steel,
}


def _frame_reinforcement(plan: PlanSchema, params: EstimatingParams) -> list[BomLine]:
    """Steel inside the concrete elements.

    Only elements that describe their members are reinforced. A volume with
    no geometry - a hand-entered pour, say - is priced as concrete and left
    bare rather than reinforced on a guess.
    """
    lines: list[BomLine] = []
    for element in plan.concrete:
        steel = _STEEL_BY_KIND.get(element.kind)
        if steel is None or not element.is_reinforceable:
            continue
        lines += steel(element, params)
    return lines
