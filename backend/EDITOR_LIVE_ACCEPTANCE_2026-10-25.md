# Correction and manual-entry acceptance — 25 October 2026

The approved correction workflow check passed through the signed-in API and the
actual browser interface against the configured Supabase project. No application
fixes, schema changes, cloud AI requests or billing changes were needed.

## Signed-in API and database checks

The dated [acceptance script](scripts/live_editor_acceptance_2026_10_25.py) created
only two clearly named test projects under the existing local test account. It
retained the older 11 October report and did not create/delete authentication users
or edit unrelated projects. [Machine-readable result](../supabase/EDITOR_LIVE_ACCEPTANCE_2026-10-25.json):
**29 assertions passed**.

- Upload/read/save of the real `01.png` floor plan returned PHP 309,364.97.
- Preview of 3.20 m wall height, 80 m2 slab, twelve columns and CHB02 price zero
  returned PHP 220,028.13 without advancing the saved project pointer.
- Save/reopen preserved effective inputs, corrections, price override and total.
- Repeating the exact save returned the same revision. Stale edits and reuse of
  a save key with changed content returned 409.
- The immutable original scan and active compatibility summary remained consistent.
- Reset saved another revision and restored PHP 309,364.97. Rescan created a new
  source revision with no carried corrections, retaining the previous source.
- Real `06.png` was refused with 422, retaining its original for manual entry.
- Unconfirmed manual entry was rejected. Confirmed manual preview/save/reopen
  preserved PHP 211,628.11, `source=manual`, and idempotent retries.

Manual inputs are synthetic acceptance values: width 10 m, length 12 m, exterior
walls 44 m, interior walls 20 m, four doors, five windows, wall height 2.70 m,
slab 80 m2 and twelve columns. They are not measured ground truth for `06.png`.

Retained API projects:

| Name | ID | Final state |
| --- | --- | --- |
| ACCEPTANCE R30 R31 EDITOR 2026-10-25 | e1fd43e1-86c2-4adb-b0e6-d90dab166a81 | Rescanned original, PHP 309,364.97; correction history retained |
| ACCEPTANCE R30 MANUAL REFUSED PLAN 2026-10-25 | e0503f62-f25e-4d99-8cb2-49468c7e6546 | Manual saved version, PHP 211,628.11 |

## Browser acceptance

The user signed in to the local preview. Their browser session uses a different
account from the script's configured test account, so two separately named browser
projects were created under that current session. Both use existing repository
sample images; no unrelated project was changed.

For **ACCEPTANCE UI CORRECTIONS 2026-10-25**:

1. Created/uploaded/scanned `01.png` and observed the original saved total.
2. Entered 3.20 m, 80 m2, twelve columns and CHB02 price zero. The preview showed
   PHP 309,364.97 -> PHP 220,028.13 while the saved summary retained the old total.
3. Saved and performed a full page reload. The new total and all three quantity
   inputs remained, CHB02 retained zero price, and the original image loaded.
4. Returned to Projects and reopened the same project; saved height remained 3.20 m.
5. Reset to original, recalculated, saved and reloaded. The total restored to
   PHP 309,364.97 with 2.70 m height, 154 m2 slab, sixteen columns and original prices.

For **ACCEPTANCE UI MANUAL 2026-10-25**:

1. Uploaded/scanned `06.png`; the actual refusal screen appeared with a reason.
2. Chose View original plan; the retained image and Enter quantities manually
   control were available without a misleading zero-price estimate.
3. Blank fields failed validation. Complete synthetic inputs without confirmation
   also failed. Entries were retained.
4. Confirmed the acceptance inputs, recalculated and saved PHP 211,628.11.
5. A full reload and then a separate Projects reopen preserved the amount,
   `Entered` provenance, quantities, original `06.png` and Manual estimate saved status.

Evidence:

- [Corrected result after reload](../tmp/acceptance-2026-10-25/corrected-reloaded.jpg)
- [Reset result after reload](../tmp/acceptance-2026-10-25/reset-reloaded.jpg)
- [Refusal with original retained](../tmp/acceptance-2026-10-25/refused-original.jpg)
- [Manual result after reopening](../tmp/acceptance-2026-10-25/manual-reopened.jpg)
- [Manual reopened visible text](../tmp/acceptance-2026-10-25/manual-reopened.txt)

The browser manual project explicitly describes its inputs as synthetic acceptance
quantities. The browser correction project was left reset to the original. All
four new test projects remain available under their respective owners for review.

## Scope and remaining work

This verifies the floor-plan correction/manual workflow on desktop, plus the
backend retry/conflict/rescan cases. It does not repeat mobile, keyboard-only,
two-user security or every electrical/plumbing field's browser acceptance. Their
existing regression coverage and earlier acceptance records remain separate.
New trade recognition accuracy, Gemini availability and real construction validity
of the synthetic manual inputs are not established. No full UI redesign was done.

The separate [representative regression report](SUBMISSION_ACCEPTANCE_2026-10-25.md)
records 661 passing non-OCR backend tests, 36 frontend/database checks, twelve
electrical image regressions and six real-image API outcomes. Those checks preceded
this live workflow verification; they were not rerun unnecessarily afterward.

Next separately confirmed task: assemble the demonstration set with explicit
successful, partial-read/corrected and refusal cases. Submission-wide limitations,
remaining product decisions and the frozen handoff snapshot remain pending.
