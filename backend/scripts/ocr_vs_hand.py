"""Compare a real OCR read against the hand transcription of the same plan.

The hand fixtures in tests/fixtures/sample_plans.py are what a perfect
reader would produce. This script runs the actual OCR path over the images
and reports the difference in the final priced estimate - the only error
measure that matters.

Needs the four plan images in tests/fixtures/plans/.
"""

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.extract.reader import read_plan  # noqa: E402
from app.extract.to_plan import extract_plan, to_plan_schema  # noqa: E402
from app.takeoff.estimator import estimate_plan  # noqa: E402
from tests.fixtures.sample_plans import CAD_SQUARE, CAD_WIDE, KERALA, NOTEBOOK  # noqa: E402

CATALOG = {
    r["item_id"]: r
    for r in json.loads((BACKEND / "tests/fixtures/catalog.json").read_text("utf-8"))
}

PAIRS = [
    ("01.png", CAD_WIDE),
    ("02.jpg", NOTEBOOK),
    ("03.png", CAD_SQUARE),
    ("04.jpg", KERALA),
]


def hand_extraction(plan):
    return extract_plan(
        plan.envelope_w, plan.envelope_l, plan.room_blocks, plan.chains, plan.opening_tags
    )


def total_for(ex):
    return estimate_plan(to_plan_schema(ex), CATALOG).grand_total


def main() -> None:
    plans_dir = BACKEND / "tests/fixtures/plans"
    missing = [f for f, _ in PAIRS if not (plans_dir / f).exists()]
    if missing:
        print(f"Missing plan images in {plans_dir}: {', '.join(missing)}")
        print("Save the four sample plans there and re-run.")
        return

    print(
        f"{'IMAGE':<9} {'PLAN':<12} {'ENVELOPE (OCR)':<17} {'ROOMS':<9} "
        f"{'WALL m':<14} {'HAND P':>12} {'OCR P':>12} {'DELTA':>9} {'CONF':>6}"
    )
    print("-" * 108)

    for filename, plan in PAIRS:
        ocr = read_plan(str(plans_dir / filename))
        hand = hand_extraction(plan)

        hand_total = total_for(hand)
        ocr_total = total_for(ocr)
        delta = (ocr_total - hand_total) / hand_total * 100 if hand_total else 0.0

        print(
            f"{filename:<9} {plan.key:<12} "
            f"{ocr.envelope_w_m:>6.2f} x {ocr.envelope_l_m:<6.2f}   "
            f"{len(ocr.rooms_m):>2}/{len(hand.rooms_m):<5} "
            f"{ocr.walls.total_m:>6.2f}/{hand.walls.total_m:<6.2f} "
            f"{hand_total:>12,.0f} {ocr_total:>12,.0f} {delta:>8.1f}% "
            f"{ocr.confidence:>6.2f}"
        )

    print()
    print("Warnings raised by the OCR read:")
    for filename, plan in PAIRS:
        ocr = read_plan(str(plans_dir / filename))
        warnings = ocr.warnings()
        if warnings:
            print(f"  {filename}:")
            for w in warnings:
                print(f"     - {w}")
        else:
            print(f"  {filename}: none")


if __name__ == "__main__":
    main()