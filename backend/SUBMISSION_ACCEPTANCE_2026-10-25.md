# Representative local acceptance — 25 October 2026

The approved bounded regression and representative local API checks passed.
Recognition limitations remain; this is not a full accuracy certification, live
deployment check or independent annotation review. Gemini was disabled for the
real-image checks; no provider requests or billing changes were made.

## Regression results

| Check | Actual result |
| --- | --- |
| Frontend TypeScript | Passed |
| Frontend production build | Passed; existing large-bundle advisory |
| Frontend/database tests (`node --test tests/*.test.mjs`) | 36 passed, zero skipped |
| Backend non-OCR (`pytest backend/tests -m 'not ocr' -q`) | 661 passed, 53 deselected, four dependency warnings; 13.60 s |
| Existing real electrical ground-truth regressions | 12 passed; 6.64 s |
| Representative real-image API checks | Six expected outcomes, all passed |

The four warnings concern FastAPI/Starlette HTTPX/BlockingPortal deprecations and
Supabase HTTP client timeout/verify configuration. Dependencies were not changed.
The 53 excluded OCR tests were not all run: the 12 electrical tests above are a
selected subset, supplemented by the six actual image requests below. Do not
represent this as the entire backend suite passing.

## Real-image API checks

Requests used the actual `/api/estimate/image` route, local OCR and installed
symbol references. Only authentication and the catalog source were replaced:
a stand-in owner and committed 52-SKU catalog snapshot were used. Audit writes
were suppressed. No Supabase projects or storage objects were created/modified.

| Trade / sample | Outcome | Details | Time |
| --- | --- | --- | ---: |
| Floor `01.png` | 200 | PHP 309,364.97, eight priced lines; 14 x 11 m envelope, ten rooms, sixteen counted columns | 2.883 s |
| Floor `06.png` | 422 | Insufficient readable room dimensions; no estimate returned | 18.741 s |
| Electrical `IMAGE/08.png` | 200 | Nineteen CLR01 light points, PHP 7,080.16, four priced lines | 0.802 s |
| Electrical `IMAGE/10.png` | 422 | Nine matched devices below the unchanged ten-device minimum; no estimate returned | 1.201 s |
| Plumbing `IMAGE/02.png` | 200 | OCR tags: eight WC, twelve LAV, thirteen FD, four CO; PHP 27,264.00 | 14.759 s |
| Plumbing `IMAGE/03.jpg` | 422 | One material-bearing fixture, below the unchanged three-fixture minimum; no estimate returned | 11.174 s |

All successful responses included structured inputs for replay. Each refusal
returned a reason rather than a zero-price estimate. These are API response
checks, not a browser evaluation of how that reason is displayed.

### Recognition limit exposed by the successful plumbing read

The previously owner-confirmed restroom reference is eleven WC / twelve LAV.
The current local tag reader recovers eight WC / twelve LAV: three WC are missed.
Its positive price and passing fixture minimum do not establish complete reading.
FD/CO totals were recorded, not independently certified. A demonstration must
explicitly review/correct quantities, or clearly disclose the partial read.
Gemini's separate failed requests do not validate an alternative automatic result.

The floor geometry and local price regression are established only for the tested
sample; structural sections/openings and pipe allowances remain as documented
assumptions. Electrical sample 08's nineteen lights do not establish switch/outlet
subtype recognition. Sample 10 remains refused despite nine real matched outlets.
No thresholds, minimum counts, takeoff constants or recognition rules were changed.

## Evidence and scope boundaries

- [Real-image response record](../tmp/acceptance-2026-10-25/representative-results.json)
  retains image hashes, status codes, quantities, extraction details and timings.
- [Local reproducibility script](../tmp/acceptance-2026-10-25/check_representative.py)
  uses real readers, snapshot catalog, stand-in authentication and disabled cloud
  calls; it suppresses audit writes and expects the six outcomes above.
- Source checkout: HEAD `dd72edea` plus the existing uncommitted working changes.
  This is not a frozen or transferred release snapshot.

Not performed here: the complete OCR test suite, a new signed-in browser session,
live database/storage acceptance, a full save/reopen/reset/manual-entry check,
fresh-family human accuracy validation or successful Gemini inference. Correction
workflow verification is the next separately confirmed task. Demonstration-set
preparation, a submission-wide limitations summary and snapshot freeze also remain.
