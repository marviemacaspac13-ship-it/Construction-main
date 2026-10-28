# Editor deployment and saved-revision contract

Task 7 was implemented and migration `006_correction_editor.sql` was applied to Construction_Main on 11 October 2026, after owner approval. It requires migrations 003–005 and the existing `ESTIMATE_REVISIONS_ENABLED=true` and `PLAN_ASSETS_ENABLED=true` backend settings. Restart the backend after pulling the new routes.

## Workflow

Open a completed project. `Correct quantities and prices` appears beside the exact original plan for the active saved source. Edit supported source fields or expand `Project material prices (PHP)`, click **Recalculate**, review the saved/revised total and changed material quantities/prices, then **Save changes**. Field resets and **Reset to original** are drafts until recalculated and saved. Reset creates another revision; it does not rewrite history.

Floor plans expose global wall height, slab area, and column count with linked footing quantities. Electrical plans expose existing outlet and ceiling-outlet variants; switches and AC remain withheld pending rule/reference review. Plumbing exposes the existing fixture tags. Blank unread counts remain unknown; explicitly entered zero is retained. Derived material quantities are read-only. Prices are overrides against the captured original catalog, local to the saved revision.

Saved originals whose automatic read was refused offer **Enter quantities manually**. Every displayed measurement/count requires an explicit entry and confirmation. Floor geometry uses separate exterior/interior wall lengths, standard opening dimensions, guide member sizes, and envelope-derived beam geometry; opening deductions apply to the first aggregate wall (exterior when present). This is a limited manual takeoff, not arbitrary geometry editing. Automatic refusal thresholds remain unchanged. A manual source retains `concrete_basis` so an excluded slab or zero column count can later be corrected to a positive quantity.

Replacement/rescan starts a separate scan revision and carries no corrections. The replacement height starts from the original scan's parameter. Existing corrected versions remain immutable. Carry-forward review/merging is not implemented; users re-enter corrections after reviewing a new scan.

## API and ownership

- `POST /api/estimate/editor/preview`: `project_id`, `scan_revision_id`, complete absolute `corrections`.
- `POST /api/estimate/editor/revisions`: the same plus `precondition.expected_active_revision_id` and `precondition.idempotency_key`.
- `POST /api/estimate/manual/preview`: owner project/asset IDs and confirmed `inputs`.
- `POST /api/estimate/manual/revisions`: the same plus the preview's captured `prices` and save precondition.

Editor requests cannot supply trusted original inputs or estimates. The backend loads the owner's immutable source and recomputes the effective input and full estimate. The database locks the project and atomically appends a revision and updates its active pointer/compatibility summary. Stale saves return 409. A retry retains its exact key and corrections; a lost response cannot duplicate a revision or rewind the pointer. The source lookup and save RPCs are service-role-only and explicitly check project ownership.

Failures retain drafts and retry keys while the screen remains mounted. Reloading or leaving loses an unsaved draft; the UI warns before leaving. Conflicts require reopening the latest saved project and reconciling entries, rather than silently rebasing them. No offline or durable draft storage is claimed.

## Contract for summary and export integration

`getProject(id)` in `src/lib/projects.ts` reads `projects.active_revision_id`, loads that immutable estimate revision and its exact `scan_revision_id`, then resolves the original asset. It replaces the compatibility summary fields with that revision's `estimate.line_items` and `estimate.grand_total` before returning. Summary cards, material table, breakdown and CSV must use that returned saved estimate. Never mix a new pointer, older source, or unsaved preview. CSV prices/totals are numeric decimals and quoted safely.

Previews are local review state and must not update saved summaries/exports. On successful save, reload with `getProject`; on failure, keep the existing displayed saved revision. Legacy rows remain readable but cannot be edited without complete original snapshots. `unpriced` and assumptions remain preserved in revision data without adding the previously removed UI panels.

This contract is available for coworker integration in the repository. No coworker message has been sent; direct coordination remains open under task 4.

## Verification

- Backend regression suite: **553 passed, 51 deselected** (non-OCR selection).
- Frontend helper/database tests: **32 passed**, including correction RPC ownership, transactions, idempotency, stale-save rejection, original immutability, explicit zero/unknown/reset behavior and CSV escaping.
- Type checking and production build passed; the existing large-bundle warning remains.
- Deployed API acceptance: **30 assertions passed**, including real OCR/upload/save, correction/retry/stale/reset/rescan and a real second-user boundary. The temporary second account was removed.
- Browser acceptance: quantities 3.20 m / 80 m² / 12 columns with CHB02 price zero changed the saved fixture estimate from **₱309,364.97 to ₱220,028.13**, survived full reload, and reset/save/reload restored **₱309,364.97**. Invalid blank height retained the other entries and focused the field-linked error summary.
- Browser manual preview/save/full reload preserved **₱211,628.11**, its entered provenance and original `06.png`. These manual measurements are synthetic acceptance inputs; they do not represent a verified takeoff of that drawing.
- Desktop1440, mobile390 and the user's973 viewport were captured. The mobile material table scrolls within its own region. Finish-review evidence is in `tmp/acceptance/editor-*.png`.

Live API evidence: `EDITOR_LIVE_ACCEPTANCE_2026-10-11.json`. Retained review projects are named `ACCEPTANCE R30 R31 EDITOR 2026-10-11` and `ACCEPTANCE R30 MANUAL REFUSED PLAN 2026-10-11`. The first has been reset to its original source quantities/prices; correction history remains intact.

Finish review: **ship within task 7 scope**. The reviewer scored the rescan-height seed, mobile table separation and manual validation copy resolved after two fix batches. Screenshot/source inspection covered the touched UI; independent computed-contrast and keyboard-scroll measurements were outside that review. The ordinary extension preserves the incumbent design system.
