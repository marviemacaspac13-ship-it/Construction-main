"""An audit trail for what each estimate was built on.

Every estimate rests on assumptions - guide sections, waste allowances,
assumed openings, an assumed frame layout, a symbol-library variant
mapping. The API returns them in `assumptions`, but nothing renders them:
that is a deliberate product decision, not an oversight.

They still need to exist somewhere. An estimate nobody can reconstruct is
an estimate nobody can check, and `RULES_VERSION` alone only says WHICH
set of rules ran, not which knobs they ran with. So each estimate appends
one JSON line here, and logs a summary the console picks up.

Written to `backend/runs/`, which is gitignored. Never let a failure to
record break the estimate itself - the audit trail is a convenience, and
the caller is waiting on a price.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("trace.estimates")

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
LEDGER = RUNS_DIR / "estimates.jsonl"

# One plan should not be able to fill a disk. Rotate rather than truncate,
# so the most recent history survives a rollover.
MAX_BYTES = 5_000_000


def _rotate_if_large() -> None:
    if LEDGER.exists() and LEDGER.stat().st_size > MAX_BYTES:
        LEDGER.replace(LEDGER.with_suffix(".jsonl.1"))


def record_estimate(plan_type: str, estimate, extraction=None, plan=None) -> None:
    """Append one line describing an estimate and everything behind it."""
    try:
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "plan_type": plan_type,
            "rules_version": estimate.rules_version,
            "grand_total": estimate.grand_total,
            "lines": [
                {"item_id": li.item_id, "quantity": li.quantity, "rule": li.rule}
                for li in estimate.line_items
            ],
            "unpriced": [li.item_id for li in estimate.unpriced],
            "assumptions": estimate.assumptions,
        }
        if getattr(plan, "fixture_tags", None):
            # Counted but never priced, so they appear in no line item.
            record["fixture_tags"] = dict(plan.fixture_tags)
        if extraction is not None:
            record["extraction"] = {
                "unit": extraction.unit,
                "envelope_w_m": extraction.envelope_w_m,
                "envelope_l_m": extraction.envelope_l_m,
                "confidence": extraction.confidence,
                "warnings": extraction.warnings,
            }

        logger.info(
            "%s estimate: %.2f, rules %s, %d assumptions, %d unpriced",
            plan_type,
            estimate.grand_total,
            estimate.rules_version,
            len(estimate.assumptions),
            len(estimate.unpriced),
        )

        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        _rotate_if_large()
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # pragma: no cover - never break an estimate over a log
        logger.warning("could not record estimate to %s", LEDGER, exc_info=True)
