# Reviewed electrical wire and conduit allowances

Implemented 26 October 2026 following approval to restore the original allowances
for reviewed supported lights and convenience outlets. This extends estimating
coverage; it does not establish general recognition accuracy or complete circuit design.

## Current behavior

New image reviews submit `estimate_scope=reviewed_device_allowances`. Included
CLR01–CLR03 and OT01–OT03 devices reuse the existing count-based conductor and
conduit rules and parameter defaults. No constants, detection thresholds, provider
settings or minimum counts were changed.

Reviewed devices and explicitly compatible boxes are still counted once per
physical assembly. The allowance helper filters its inputs to the supported light
and convenience-outlet SKUs; it does not generate additional boxes. Excluded
devices add no allowances. Omitting a box explicitly does not remove the supported
device's wire/conduit allowance.

SW01–SW03 and ACO01 can contribute their reviewed devices and confirmed compatible
boxes under the existing classification restrictions. They contribute no wiring
allowance. Breakers, panels and circuit design remain excluded. Quantities are
estimating allowances, not traced or measured circuit routes.

Upload, review, results and CSV describe this boundary without identifying the
detection implementation. Reviewed counts remain tied to their assemblies;
project prices can still be edited, reset and saved as a new version.

## Historical compatibility

The earlier `devices_and_boxes` scope retains its original material lines,
exclusions and totals. Existing saved estimates are not silently upgraded or
repriced. Replace/rescan and confirm a new review to apply the restored scope.
The legacy direct estimating path is unchanged.

## Validation

- 750 backend non-OCR tests passed; 53 OCR tests deselected because image readers
  and detector settings were unchanged. The 14 new regression cases cover all six
  supported variants, mixed inventories, exclusions, box omissions, old-scope
  replay, price changes/reset, tampered counts, image estimation and server-side
  revision recomputation.
- 40 frontend/storage checks passed; TypeScript and production build passed.
- The interface detector found no issues in the five changed UI files. The live
  upload screen displays the new scope; screenshot:
  `../tmp/electrical-allowances-2026-10-26/upload.png`.
- Restarted the verified local backend to load the changes.
- No model/provider requests or saved-project writes were made for these checks.

An offline replay of the existing nine-light test inventory against the committed
catalog produces 9 CLR01 devices (₱198), 115.83 m ELW05 wire (₱2,779.92), and
35.64 m FPVC01 conduit (₱213.84): **₱3,191.76**. The same six excluded switches
and nine omitted boxes remain excluded. The saved historical result stays ₱198.
This comparison verifies arithmetic and scope, not measured-route accuracy or live
catalog prices. Evidence: [allowance replay](datasets/electrical-gemini-validation-2026-10-26/allowance-replay.json).
