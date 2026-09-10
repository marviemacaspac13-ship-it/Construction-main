"""Run the full extraction -> rules -> pricing path over the sample plans.

Offline: prices come from the committed catalog snapshot, so this needs no
Supabase connection and no network.

    ./.venv/Scripts/python.exe scripts/estimate_samples.py
"""

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.extract.to_plan import extract_plan, to_plan_schema  # noqa: E402
from app.takeoff.estimator import estimate_plan  # noqa: E402
from tests.fixtures.sample_plans import ALL_PLANS  # noqa: E402

CATALOG = {
    row["item_id"]: row
    for row in json.loads(
        (BACKEND / "tests" / "fixtures" / "catalog.json").read_text(encoding="utf-8")
    )
}


def peso(n: float) -> str:
    return f"P{n:,.2f}"


def main() -> None:
    grand = 0.0
    for plan in ALL_PLANS:
        ex = extract_plan(
            plan.envelope_w,
            plan.envelope_l,
            plan.room_blocks,
            plan.chains,
            plan.opening_tags,
        )
        schema = to_plan_schema(ex)
        result = estimate_plan(schema, CATALOG)
        grand += result.grand_total

        print("=" * 78)
        print(f"{plan.key.upper()}  -  {plan.description}")
        print("=" * 78)

        print(f"  units      : {ex.units.note}")
        print(
            f"  envelope   : {ex.envelope_w_m:.2f} x {ex.envelope_l_m:.2f} m "
            f"= {ex.area.envelope_area_m2:.1f} m^2"
        )
        chain_bits = " ".join(
            f"[{'ok' if c.ok else 'FAIL'} {c.total:g}/{c.stated_total:g}]"
            for c in ex.chain_checks
        )
        print(f"  chains     : {chain_bits}")
        if any(c.dropped_cumulative for c in ex.chain_checks):
            dropped = [v for c in ex.chain_checks for v in c.dropped_cumulative]
            print(f"               dropped cumulative marker(s): {dropped}")
        print(f"  rooms      : {len(ex.rooms_m)} read, {ex.area.room_area_m2:.1f} m^2")
        print(
            f"  walls      : exterior {ex.walls.exterior_m:.2f} m + interior "
            f"{ex.walls.interior_m:.2f} m = {ex.walls.total_m:.2f} m"
        )
        print(
            f"  openings   : {ex.doors} doors, {ex.windows} windows"
            + ("" if (ex.doors or ex.windows) else "  (none tagged)")
        )
        print(
            f"  area check : {ex.area.accounted_ratio:.0%} of envelope accounted "
            f"({ex.area.unaccounted_m2:g} m^2 unexplained)"
        )
        print(f"  CONFIDENCE : {ex.confidence:.2f}")
        for warning in ex.warnings():
            print(f"  ! {warning}")

        print()
        print(f"  {'SKU':<8} {'MATERIAL':<26} {'QTY':>10}  {'UNIT PRICE':>12}  {'TOTAL':>14}")
        print("  " + "-" * 76)
        for li in result.line_items:
            print(
                f"  {li.item_id:<8} {li.item_name[:26]:<26} {li.quantity:>10,.2f}  "
                f"{peso(li.unit_price):>12}  {peso(li.line_total):>14}"
            )
        print("  " + "-" * 76)
        print(f"  {'GRAND TOTAL':<48}{peso(result.grand_total):>28}")
        print()

    print("=" * 78)
    print(f"All four sample plans: {peso(grand)}")
    print("=" * 78)


if __name__ == "__main__":
    main()