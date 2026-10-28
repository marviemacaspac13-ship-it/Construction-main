# Electrical audit/alignment checkpoint — 28 October 2026

Completed the user-approved saved-response error audit and one bounded backend
improvement. [Full evidence and diagnosis](datasets/electrical-error-audit-2026-10-27/README.md).

- Audited 63 sample/model reference rows across four saved outputs on three
  previously exposed sheets. Kept misses, displaced markers and class errors
  separate. Found an ACU subtype ambiguity in the legacy power reference ledger;
  did not relabel the model's AC device or alter frozen scoring to improve results.
- Added one conservative follow-up alignment pass: only an original-nearest,
  never-attempted anchor may be reconsidered after competing alternatives are
  already owned by successful first-pass assignments. No new devices/classes,
  threshold/ring/minimum changes, price changes or additional model attempts.
- Saved-output replay: lighting sheet 08 **13 → 14 of 19** correct under the
  fixed 20 px same-class rule; power sheet 10 remains 7/14; sheet 11 remains 8/15
  and 7/15 for its two models. The gain is one moved marker, not new-device recall.
- Two reviewer-discovered competitor/priority cases were reproduced and fixed.
  Re-review found no remaining actionable issue in the fixes.
- **58** focused tests and **785** non-OCR backend tests passed; **53** OCR tests
  deselected. Existing dependency warnings remain. No new frontend build was
  needed for this backend-only patch.
- Local backend restarted with the change. Existing saved estimates unchanged;
  unsaved receipts from the previous process require a fresh scan. No new provider
  calls, live acceptance writes, commits, packaging or release freeze performed.

R25 remains partial. The next substantive gate is subtype-correct, independently
checked references and a bounded trial aimed at missing devices or class reading.
The earlier submission-packaging work remains stopped and was not resumed here.
