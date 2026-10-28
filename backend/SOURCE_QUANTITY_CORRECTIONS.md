# Source-quantity recalculation — TODO 5

Task 6 now adds [project price overrides](PROJECT_PRICE_OVERRIDES.md) to the same
endpoint. Quantity semantics below remain unchanged.

Implemented 11 October 2026. `POST /api/estimate/recalculate` requires the normal
signed-in bearer token and returns a computed preview. It reads no project or
catalog from Supabase, invokes no recognition, and writes no saved revision.
The audit ledger records the correction values and reason alongside the estimate.

## Request and response

Send `original_input` (the complete original scan snapshot) and `corrections`
(the complete current `EstimateCorrections` record). The response contains
`effective_input`, validated `corrections`, and `estimate`. The frontend client
is `recalculateEstimate` in `src/lib/estimate.ts`.

Every call starts from a deep copy of the original. Overrides are absolute, not
increments. Omit/remove an override to reset it; do not send the previous effective
snapshot as the original. The original captured prices, purchase units and capture
time remain unchanged. The computed estimate receives a new calculation timestamp.
Rule or purchase-unit incompatibility returns 409. Invalid corrections, wrong-trade
fields, non-finite inputs and insufficient geometry return 422.

This is a stateless preview, not proof that a caller supplied an authentic stored
scan. Task 7 must load and authorize the immutable scan on the server, recompute
from its original input, and save with the existing concurrency/idempotency rules.
The scan-save endpoint is not a correction-save endpoint. No deployment migration
is needed for this task; restart the backend to expose the new route.

## Quantity semantics

| Override | Effective input and dependent calculations |
| --- | --- |
| `wall_height_m` | Replaces the project default and every wall's explicit height. Masonry, mortar, wall reinforcement and tie wire recalculate. Member sections, column heights, beams and slabs remain unchanged. |
| `slab_area_m2` | Sets total explicit area on `slab_on_grade`; concrete uses area × retained thickness, and mesh uses that same area. Width/length and all other members remain unchanged. |
| `column_count` | Replaces counts in the original `columns` and linked `footings` groups. Rebuilds both volumes from their retained member dimensions; concrete, bars, ties and tie wire recalculate. No detector plausibility fallback. |
| `electrical_counts` | Replaces the aggregate count for each supplied supported SKU, including duplicate original groups. Other SKUs remain unchanged. Existing device, box, conductor and conduit rules rerun. Measured routes retain precedence. |
| `plumbing_counts` | Replaces supplied canonical fixture tags; all others remain unchanged. Existing branch, fitting and main-run rules rerun, including changing main drain size when the last WC is removed. Cleanouts remain counted-only. |

Null/omitted scalar overrides mean unchanged. Zero area removes the slab; zero
columns removes columns and their linked footings. Zero device/tag counts are
retained explicitly and contribute no derived purchases. Unknown counts are not
coerced to zero. Counts reject strings, fractions, booleans and negatives. Height
and area reject strings, booleans, negative/non-finite numbers; height must be
greater than zero and at most 10 m.

Frame corrections require the existing canonical member groups, complete geometry
and matching original column/footing counts. Missing, multiple or ambiguously
linked members are refused. This deliberately supports current image-generated
snapshots; it does not invent geometry for legacy records or refused scans.
Task 7's separate manual-input workflow remains unimplemented.

`ConcreteElement.slab_area_m2` and `PlanSchema.manual_column_count` are additive,
optional version-1 fields. Old snapshots retain their original behavior. Explicit
slab area must agree with the serialized concrete volume; inconsistent geometry
is rejected. The manual count records provenance, including intentional zero, so
the estimate does not claim those columns were detected or placed by spacing.

## Supported scope

Electrical keys retain the contract's existing GS01–03, SW01–03, OT01–03, ACO01,
CLR01–03 products. This executes current rules, not new switch/AC classification
or a claim of complete wiring allowances. Those categories still require review
before the editor presents them as reliable complete estimates. Plumbing accepts
`water_closet`, `lavatory`, `urinal`, `floor_drain` and `cleanout`. New classes and
panel/breaker corrections are rejected.

Task 6 accepts `unit_prices` against a copy of the captured catalog. Automatic recognition
minimum-count guards are unchanged; an explicitly corrected zero is distinct from
an automatic reader finding nothing. No editor or corrected-revision save is added
here; those remain task 7.

## Verification

- 515 non-OCR backend tests passed; 51 OCR tests deselected. This includes 48 new
  correction tests and authenticated-route regression coverage.
- A separate real `01.png` read/correct/reset test passed: OCR ran once, corrections
  changed height/slab/columns, and reset reproduced the original material lines.
- Tests cover immutable originals, replay, zero exclusions, implausible-but-confirmed
  counts, dependent quantities, merged lines, waste, purchase-unit rounding, missing
  prices, existing device keys, malformed inputs, incompatible versions/units,
  wrong-trade requests, API responses and audit recording.
- Frontend type checking and production build passed. The existing bundle-size
  warning remains. TestClient and Vite required execution outside the Windows
  sandbox; the sandboxed runs stalled or failed at `realpath`.

No live Supabase deployment or browser editor acceptance was needed or claimed for
this computation-only task. Existing persistence regression tests passed.

Task 7 update, 11 October 2026: the Results editor, immutable correction saves, reset, manual-source flow and live acceptance are now implemented. See [editor deployment and integration contract](../supabase/EDITOR_DEPLOYMENT.md).
