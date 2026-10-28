# Electrical allowance live workflow test

26 October 2026. User requested a live test after restoring wire/conduit
allowances. One new browser scan used internal electrical sheet `11.png`
(683 × 658) in the existing named test project
`ACCEPTANCE GEMINI ELECTRICAL LIVE 2026-10-26`.

## Observed results

- Gemini 2.5 Flash timed out after 20.005 seconds; Flash-Lite returned HTTP 404
  after 0.579 seconds. No usable Gemini proposals were returned. There were no
  additional scan retries, paid-model changes or model-discovery requests.
- Automatic local fallback opened review with nine light points. All nine
  locations were checked against the original image. CLR01 was an explicit test
  product choice, not an image-derived receptacle size.
- Six visible switch marks were added manually and explicitly excluded because
  product/function and compatible box details were unconfirmed. Nine light boxes
  were explicitly omitted because compatibility was not established. A misplaced
  manually added switch marker was corrected before confirmation.
- The reviewed image request and revision save both returned HTTP 200. Results
  displayed `reviewed_device_allowances` coverage, estimating-allowance wording,
  and six device/nine box exclusions.

| Material | Quantity | Unit price | Cost |
| --- | ---: | ---: | ---: |
| CLR01 ceiling receptacles | 9 | ₱22 | ₱198.00 |
| ELW05 wire | 115.83 m | ₱24 | ₱2,779.92 |
| FPVC01 conduit | 35.64 m | ₱6 | ₱213.84 |
| Total | | | **₱3,191.76** |

Full-page reload retained the total, original image, all fifteen review markers,
scope and exclusions. CSV export retained the three material quantities and
prices, the quantity-basis note and every exclusion.

The live price editor changed ELW05 from ₱24 to ₱25 per metre, previewed and saved
₱3,307.59 without changing 115.83 m. Reset to original, recalculate and save
restored ₱3,191.76. These are new revisions of the existing test project; the
historical ₱198 device-only result was not silently repriced by the deployment.
Returning to Projects and reopening the named test project retained the restored
₱3,191.76 total, all three material quantities, all fifteen review markers and
the same scope/exclusions. The browser was left on this saved result.

## Interpretation

The light allowance calculation, reviewed exclusions, revision saving, reload,
export and price correction/reset passed this live test. The original offline
calculation and the live catalog calculation agree on this sample. This is a
partial lights-only test scope, not the complete building's electrical cost.
Switch/AC wiring, breakers, panels and circuit design remain excluded. A live
convenience-outlet image was not tested in this run; all six supported light/outlet
SKU variants were covered by the preceding offline regression checks.

Gemini detection improvement remains unverified. The six missed switches still
required manual marking/exclusion; this test does not close R25 recognition
acceptance or demonstrate reduced review workload.

Evidence: [audit and CSV checks](datasets/electrical-gemini-validation-2026-10-26/allowance-live-test.json).
Screenshots and exported CSV: `../tmp/electrical-allowances-live-2026-10-26/`.
