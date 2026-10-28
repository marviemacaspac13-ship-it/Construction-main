# Grouped electrical review — 27 October 2026

Implemented the user's selected improvement: device-type groups linked to the
plan, shared decisions for explicitly selected included devices, individual
exceptions, and a final quantity/exclusion summary. This changes review effort,
not recognition or electrical estimating coverage.

## Behavior

- The initial group and group buttons select included devices of that type and
  highlight those markers. Checkboxes narrow the target set. Excluded devices
  remain visible/editable but cannot silently re-enter shared decisions.
- Apply a product, compatible box decision, or reasoned device exclusion to the
  checked devices. Unknown types require individual classification first.
- Switch product assignment requires explicit confirmation of one-way function
  and matching gang count. The subsequent shared-confirmation improvement below
  allows that decision once for the selected group without inferring either.
- Product changes invalidate box compatibility. Shared box confirmation resets
  when the selection, choices or decision action changes. Each included assembly
  still requires compatibility confirmation or an explicit box exclusion reason.
- Shared updates are atomic. Errors leave all choices intact. Unselected choices
  and observation geometry/identity remain intact. One-step Undo shared decision
  restores the previous choices; subsequent individual changes clear that undo
  snapshot so it cannot overwrite later edits.
- The final summary shows included/excluded counts, selected product/box counts
  and grouped device/box exclusion reasons. Existing final drawing/scope
  confirmation and geometry/refusal guards remain in effect.
- Existing individual editing, additions, movement and keyboard resizing remain.
  Saved JSON contracts, server checks, prices and historical results are unchanged.

## Verification

- New shared-decision tests failed before implementation and passed afterward.
  All 44 frontend/storage tests passed, including seven electrical-review tests.
- TypeScript and production build passed. Build retains its large-chunk warning.
- Impeccable's mechanical UI detector returned no findings.
- Browser checks used the archived sheet-08 response and local original image in
  `tmp/electrical-group-review.html`; no recognition/provider calls or project
  writes. This is a clearly labelled offline fixture, not recognition acceptance.
- Checked 15-light shared product/box exclusion while leaving one unchecked light
  unchanged, then resolved that exception with a different product and explicit
  compatible box. Checked nine shared switch exclusions and final confirmation.
- Checked shared box assignment, undo, and final quantity/exclusion summary.
- Focused review found stale shared box confirmation after selection/product
  changes. Fixed and reproduced the refusal in the browser: confirming then
  changing the selection requires a fresh confirmation. Re-review found no
  remaining actionable issue in this fix.
- At a 390-pixel iframe viewport the document width and scroll width were both
  375 pixels (excluding its scrollbar); shared product application worked.
- Desktop screenshot: `tmp/electrical-group-review-desktop.png`.

At the initial UI checkpoint, no new live save/reopen acceptance was performed; the existing integration and
storage contract remain unchanged. Draft persistence is not part of this change.
R25 recognition acceptance and switch/AC circuit material support remain open.

## Follow-up: shared switch specification confirmation

After the user encountered the switch guard, they approved one shared
confirmation of the selected product's one-way function and gang count. The
product panel now names both attributes and the number of selected assemblies.
Checking it fills missing specifications in each reviewed choice, preserving
the raw proposal observations, geometry and identity. Nonnull conflicting gang
counts or three-way/four-way functions are flagged on their individual rows and
block the entire update; they must be edited or unchecked explicitly.

The confirmation resets on product, action, selection and choice changes.
Product assignment still invalidates box compatibility and does not add wiring
support. No backend contract or pricing change was required.

Verification: both new regression tests failed before implementation and passed
afterward; all 46 frontend/storage tests, TypeScript and build passed. The UI
detector returned no findings, and focused review found no actionable regression.
A separate offline browser fixture verified the SW03 conflicts, selection-reset
behavior and applying SW01 to five matching assemblies while leaving four
conflicting switches unchanged. Screenshot:
`tmp/electrical-shared-switch-confirmation.png`. No provider calls or project writes.

## Later authenticated acceptance checkpoint

The [live acceptance](ELECTRICAL_GROUPED_LIVE_ACCEPTANCE_2026-10-27.md) subsequently
passed component/API save, exact retry, full reload, actual Projects/Results reopen,
CSV and project-price edit/reset. Local fallback supplied 19 lights; one added
switch was explicitly synthetic. The project is retained reset to PHP 6,911.16.
Three new backend snapshot cases passed; latest checks are 776 non-OCR backend
tests (53 deselected), 46 frontend/storage tests and typecheck/build. The alternate
New Project modal now repeats UploadScreen's electrical scope copy. No provider
requests were made; general recognition acceptance remains open.
