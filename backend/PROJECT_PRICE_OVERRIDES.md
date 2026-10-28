# Project-specific price overrides — TODO 6

Implemented 11 October 2026. The authenticated `POST /api/estimate/recalculate`
endpoint now accepts `corrections.unit_prices`: absolute PHP prices per captured
purchase unit, keyed by SKU. For example, send this correction record alongside
the complete `original_input` snapshot:

```json
{
  "quantities": {},
  "unit_prices": {"CMT01": 300, "DB01": 175.25},
  "reason": "Supplier quotation"
}
```

The response keeps the existing `effective_input`, `corrections` and `estimate`
structure. The frontend `recalculateEstimate` client already accepts this shape.
Editing controls and saved correction revisions remain task 7; no button is added.

## Price identity and reset

The original snapshot captures the catalog prices, display units and machine
purchase-unit specifications. `PriceSnapshot.with_overrides` validates and copies
it, replacing only the supplied prices. It never reads or writes the live catalog.
Separate project drafts receive independent copies, even with the same original.

The effective snapshot's content hash reflects the resulting prices and metadata.
Identical content has the same hash regardless of override order. `captured_at`
retains the original catalog capture time; `estimate.priced_at` records the new
calculation. Corrections preserve the supplied prices and optional reason, which
also appear in the audit ledger. The unchanged original is the reset basis.

Supply the complete current override set each time. Remove a SKU to reset that
price; send an empty price map to reset all prices while keeping any quantity
overrides. Always rebuild from the original, not the previous effective snapshot.

Price-only edits preserve plan geometry, parameters, quantities, purchase units,
derivations and unpriced quantities. Lines may reorder because they sort by cost.
Existing quantity rounding applies; line totals are quantity × price rounded to
two decimal places, and the grand total sums those totals. Unit prices may retain
fractional precision. No tax, delivery or supplier assumptions are added.

## Validation and missing prices

- Prices must be finite, nonnegative JSON numbers. Booleans, strings, null,
  negative values and arithmetic overflow return 422.
- Zero is intentional: the line keeps its quantity with zero cost and remains
  priced, rather than becoming unresolved.
- A SKU must have a supported purchase unit and a row in the captured catalog.
  A price alone cannot supply missing names, categories or purchase units.
- Missing rows remain in `unpriced`; overriding a missing row is refused. An
  explicitly reviewed catalog refresh or metadata-complete workflow is needed.
- Captured but unused supported SKUs can have overrides. This creates no purchase;
  a later quantity correction can use that price.
- Incompatible rules or purchase units still return 409. Price editing cannot
  silently adopt changed stick lengths or quantity rules.

## Explicit catalog refresh contract

Reopening and normal recalculation never refresh prices. A future user-selected
refresh must capture the selected catalog with its own timestamp/hash, check unit
compatibility, show price differences, and require review before carrying existing
overrides onto the refreshed basis. It must save a new immutable estimate revision
linked to the same scan, using the expected active revision and idempotency key.
Earlier revisions and the scan's original catalog remain unchanged.

That revision must retain its selected base price snapshot as well as effective
prices and corrections, so resetting and reopening have an explicit price basis.
The current request uses the original scan basis only. Refresh execution and its
additional revision metadata/UI are future work; clearing overrides is not refresh.

## Persistence boundary and verification

The result serializes through the existing `EstimateRevision` contract. Replaying
effective inputs, or rebuilding from original inputs and corrections, produces
the same costs without querying today's catalog. Task 7 must authorize the stored
project/scan, recompute and save atomically. A client-supplied preview is not an
authorized saved revision; do not reuse scan-save to overwrite the original.

Verification: 539 non-OCR backend tests passed, 51 OCR tests deselected. The 24 new
price tests cover unchanged quantities/metadata, independent project drafts,
partial/full reset, zero, missing rows, unused SKUs, hashes, validation, rounding,
overflow and API/audit behavior. A file round-trip of the original snapshot and
`EstimateRevision` verifies reopening/replay after simulated live price changes;
this is contract verification, not live Supabase correction saves or browser
acceptance. Frontend type checking passed. No database migration is required.

Final client-price acceptance still needs the dated price list and agreed
tax/delivery conventions. Editor save/reopen acceptance remains task 7.

Task 7 update, 11 October 2026: the Results editor, immutable correction saves, reset, manual-source flow and live acceptance are now implemented. See [editor deployment and integration contract](../supabase/EDITOR_DEPLOYMENT.md).
