# Grouped electrical review acceptance — 27 October 2026

Authenticated component/API, real database/Storage and production Results checks
passed. The review component ran in a local acceptance harness against a separate
backend at port 8001 with electrical/plumbing external recognition disabled.
No provider images were sent, model quotas consumed, persistent environment files
changed, unrelated projects edited or stored objects deleted.

## Retained project and test inputs

`ACCEPTANCE GROUPED ELECTRICAL 2026-10-27` is retained under the existing signed-in
owner. Its description explicitly marks manually added switches as synthetic
workflow inputs. Source: repository electrical `IMAGE/08.png`.

- Local fallback supplied 19 light proposals. No switch recognition is claimed.
- Shared choices assigned CLR01 to the lights, with explicit box exclusions.
- Device 1 was individually changed to CLR02, preserving the other 18 CLR01 choices.
- One synthetic assembly was added on the plan, identified as a switch and marked
  `SYNTHETIC WORKFLOW INPUT`. Shared confirmation selected SW02/two-gang/one-way;
  its box was explicitly excluded. This is one purchased set, not two switches.
- Final review: 19 raw proposals, 20 reviewed choices, 18 CLR01 + 1 CLR02 + 1 SW02;
  20 reasoned box omissions. No device was excluded in this particular live fixture.
  Grouped device exclusions/conflict handling and compatible-box decisions were
  separately checked in the earlier offline UI evidence.

## Actual results

| Check | Observed result |
| --- | --- |
| Estimate and first save | PHP 6,911.16; `reviewed_device_allowances`; five priced material lines |
| Exact save retry | Same revision ID; no duplicate revision |
| Reopen through project service | Canonically equal accepted choices; equal total; exact original asset linkage |
| Full acceptance-page reload | Saved original/review, 19 raw/20 reviewed records and synthetic SW02 specifications retained |
| Real Projects → Results | Correct scope, 20 markers, individual CLR02 exception and original image displayed |
| Real Results CSV | Scope, explicit exclusions and SW02 row retained; five line totals sum to PHP 6,911.16 |
| Project-only price edit | SW02 price 169 → 170; preview PHP 6,911.16 → 6,912.16 |
| Save and full Results reload | PHP 6,912.16 retained; reviewed assemblies/partial scope unchanged |
| Reset, recalculate, save and full reload | PHP 6,911.16 restored; immutable revision history retained |

Wire is 244.53 m of ELW05; conduit is 75.24 m of FPVC01, both derived from the
19 supported lights. The switch adds no wiring allowance. Other lines are
18 CLR01, 1 CLR02 and 1 SW02. Amounts use the actual captured catalog, not newly
approved prices or synthetic circuit design.

## Verification and evidence

- Focused backend review/partial/allowance/revision checks: **79 passed**.
- Three new SW01/SW02/SW03 snapshot cases passed on existing implementation:
  unknown raw attributes stay unknown, reviewed attributes persist, device/box
  counts remain one set/one box and no switch wiring appears. No backend fix was needed.
- Full non-OCR backend run: **776 passed, 53 deselected**, four existing dependency
  deprecation warnings. Electrical/plumbing external recognition was disabled;
  model/auth/catalog network boundaries remain mocked in offline tests.
- Frontend/storage suite: 46 passed after the alternate modal copy change;
  TypeScript/build passed and the UI detector found no issues. Both actual upload
  entry points displayed the electrical scope wording. The unsaved guidance-only
  drafts were discarded without scanning or creating projects.
- Package/clean-extraction verification was not started before the user requested
  stopping at this checkpoint; no release snapshot is claimed.
- [Reloaded choices](../demo/2026-10-27/evidence/reopened-review.json)
- [Actual CSV](../demo/2026-10-27/evidence/grouped-electrical.csv)
- [Reset and reopened Results](../demo/2026-10-27/evidence/grouped-results-reset.png)

This uses the real review component and production Results/editor, but initial
preparation uses the explicit local harness rather than a new normal UploadScreen
scan through a provider. It establishes workflow/persistence, not drawing-level
switch recognition, engineering design validity, new-family accuracy or every
possible browser/owner combination. Historical `devices_and_boxes` preservation
is covered by the regression suite; historical saved projects were not rewritten.
