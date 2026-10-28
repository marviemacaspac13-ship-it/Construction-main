# Estimate input and revision contract — version 1

Task 6 update: [project-specific price overrides](PROJECT_PRICE_OVERRIDES.md) now
produce a hashed effective catalog while retaining the original prices and units.
The editor and corrected-revision saves remain task 7.

Update, 11 October 2026: task 5 now implements source-quantity recalculation.
See [correction API semantics and verification](SOURCE_QUANTITY_CORRECTIONS.md).
Its optional slab-area/manual-count fields are additive; old snapshots still
replay unchanged. References below to future correction execution record the
original task 1 design. The editor and corrected-revision saves remain task 7.

Implemented 10 October 2026 as item 1 of [the revision TODO](../todo.md). This document records that foundation. Item 2 now implements scan persistence through FastAPI replay and a service-only transactional Supabase function: see [deployment and verification](../supabase/REVISION_DEPLOYMENT.md). The historical descriptions below of persistence as future work describe the item 1 boundary; item 2 supersedes them. No correction editor or correction execution is enabled yet.

## Verified baseline

| Check | Before this change | After this change |
| --- | --- | --- |
| Non-OCR backend suite | 389 passed; 49 deselected | 414 passed; 49 deselected |
| Production frontend build | Passed; oversized-bundle warning | Passed; same warning |
| Frontend type checking | No configured command; misnamed configuration | `npm run typecheck` passes |

The existing real floor-plan image end-to-end test also passed after the change (1 passed). The remaining OCR suite was not rerun: recognition/preprocessing and quantity rules were unchanged.

The pre-change backend result was verified using an isolated temporary copy of the original `main.py` and `extract/report.py` from HEAD, with the two new test files excluded. Workspace files were not replaced. The additional 25 tests cover snapshot replay, content identity, correction validation and the three image response paths.

Initial sandboxed attempts encountered a Vite `realpath` permission error and stalled FastAPI TestClient calls. Both checks completed outside that sandbox. Existing test warnings concern Starlette/httpx, anyio and Supabase client deprecations. No test failures were observed in the completed non-OCR runs. Image recognition thresholds, guide rates, estimating formulas and catalog values were unchanged.

TypeScript 5.9.3 and React 18 type definitions are explicit locked development dependencies. `tsconfig.json` replaces `tsconfi.json`, retains strict checking, and includes all of `src/`. No suppression or excluded UI directory was needed to obtain a passing check. `npm run build` remains the production build command; run type checking separately.

## Source input inventory

The original `PlanSchema` is the canonical computation input. Extraction reports contain rounded display values and must not be used to reconstruct it.

| Requested correction | Existing source representation | Version 1 correction field | Later implementation requirement |
| --- | --- | --- | --- |
| Wall height | `params.default_wall_height_m`; optional explicit `walls[].height_m` | `quantities.wall_height_m` | Define explicit-wall precedence; recompute masonry and wall reinforcement |
| Slab area | Slab member width × length; stored concrete volume | `quantities.slab_area_m2` | Add a shared explicit area basis for both concrete volume and mesh; preserve envelope dimensions |
| Column count | Column/footing `concrete[].count`, member dimensions and volumes | `quantities.column_count` | Rebuild columns and linked footings; bypass detector plausibility fallback for confirmed manual counts |
| Electrical counts | `fixtures[]` keyed by item ID | `quantities.electrical_counts` | Validate the approved device meaning and recompute appropriate boxes/wiring; current SKU semantics are not PEC type verification |
| Plumbing counts | `fixture_tags` keyed by canonical tag | `quantities.plumbing_counts` | Recompute approved branches, fittings and main allowances |
| Material prices | Complete captured catalog | `unit_prices` keyed by item ID | Apply project-only overrides to a copy of the snapshot; recalculate totals |

Version 1 electrical correction keys: GS01–03, SW01–03, OT01–03, ACO01 and CLR01–03. These describe existing products; they do not resolve GS/SW ambiguity, gang versus way semantics, or the current switch/AC allowance issue. Panel/breaker corrections and newly classified products are outside this initial list.

Version 1 plumbing correction keys: `water_closet`, `lavatory`, `urinal`, `floor_drain`, `cleanout`. Cleanouts remain counted-only. Kitchen sinks and other new classes require approved takeoff rules first.

Counts are strict non-negative integers, rejecting booleans, numeric strings and fractional values. Height is finite, greater than zero and at most 10 m. Area and unit prices are finite and non-negative. Unknown correction fields, device IDs, fixture tags and price SKUs are rejected. These validators belong to the new correction contracts; they do not retroactively change the existing `/api/estimate` input behavior.

Null or absent scalar values mean no override. A zero count, zero slab area or zero unit price remains an intentional value. The future correction service must implement component exclusion for zero area/count without creating invalid zero-volume concrete elements. This foundation does not execute those semantics yet.

## Additive image response

`POST /api/estimate/image` continues returning `extraction` and `estimate`. It now also returns:

```text
original_input
  schema_version: 1
  rules_version: current takeoff rules identifier
  plan: exact PlanSchema passed to the rule engine
  params: complete resolved EstimatingParams
  prices
    snapshot_id: SHA-256 of canonical catalog content
    captured_at: UTC pricing timestamp
    currency: PHP
    items: all captured catalog rows and their purchase-unit specifications
scan
  source_sha256: SHA-256 of the uploaded bytes
  pipeline_version: image-v1
  method: ocr | tags | detection
unmatched_detections: electrical hits rejected for lacking a UnitSpec
```

`estimate.unpriced` retains its full BOM entries: item ID, quantity, rule, derivation and inputs. It is different from `unmatched_detections`: a recognized/usable SKU can generate a material line with no price, while an unsupported detection cannot be converted to a priced source fixture at all. Both must be retained by item 2's save workflow.

The original input is returned for all successful plan types, even where `extraction` is null. Plumbing therefore retains client-supplied fixture counts that never appear as purchasable material lines. Electrical source counts remain distinct from derived wire, conduit and boxes. All automatic refusal guards remain active.

The current Supabase saving function still saves only its existing fields; durable storage of the new snapshot is item 2. Older saved rows lack it and must not be treated as editable full-input records. Restart the backend to expose the new response. The updated frontend types expect that response; existing rendering does not yet consume the new fields.

## Price identity and replay

`PriceSnapshot` records every catalog row, including presently unused products, so later count corrections can introduce another already-supported SKU without silently using today's prices. A row captures item ID, name, display unit, category, price, and the machine-readable `UnitSpec` where available. Null purchase-unit metadata remains explicit for unsupported rows. Catalog display strings are never parsed as purchase-unit rules.

The content hash is independent of catalog row order and capture time. Changing a price, display unit, description, category or purchase-unit specification changes the hash. Parsing the snapshot checks its hash and duplicate item IDs. The hash detects inconsistent content; it is not a signature or an authorization mechanism.

`PriceSnapshot.to_catalog()` provides the captured pricing rows for replay. With the recorded rule version and corresponding purchase-unit implementation, `estimate_plan(snapshot.plan, snapshot.prices.to_catalog(), snapshot.params)` reproduces material quantities and costs without consulting Supabase. A new pricing timestamp may be generated; it is not part of numeric equality. The replay test verifies unchanged line items and total after the live catalog price changes.

Historical formula execution is not implemented. A rules-version mismatch must require an explicit new estimate or a retained compatible engine; a version label alone does not archive executable rules. Likewise, this snapshot is sufficient for cost replay, not for reproducing recognition. Detector/OCR/template artifact manifests and accepted-location evidence are future scan-revision extensions. The uploaded byte checksum only identifies the source file; the image itself will be stored in item 2.

## Original and effective inputs

On the first scan, `original_input` describes the exact input used to produce `estimate`. It is never overwritten by later corrections. `EstimateCorrections` records absolute replacement quantities and per-project unit prices, with an optional reason.

A future correction service will produce an `effective_input` by validating the overrides and rebuilding affected source geometry from the original snapshot. Repeated editing must rebuild from that original plus the current complete override set, rather than repeatedly mutating the previous computed result. Reset removes overrides and returns to the original input/price basis.

`EstimateRevision` defines the later persisted output: revision ID, scan revision ID, parent revision ID, authenticated author, timestamp, corrections, effective input and complete estimate. The model checks that plan type and rules version agree between input and output. It does not prove that the client supplied a correctly computed total; the persistence implementation must accept server-computed outputs and verify the ownership of every reference.

Python contracts live in `app/takeoff/contracts.py`; the frontend equivalents live in `src/lib/estimate-input.ts`. Dates and UUIDs serialize as strings. TypeScript describes data shape; server validation remains authoritative. Bump `schema_version` for incompatible input changes and add a deliberate migration, rather than silently coercing older snapshots.

## Immutable revisions and concurrency specification for item 2

The proposed storage records are plan assets, scan revisions and estimate revisions, linked to the existing owner-scoped project. A project points to its active revision. The database must enforce append-only scan/estimate records; Python model instances alone do not enforce database immutability.

An atomic save accepts the computed revision and `RevisionSavePrecondition`:

- `expected_active_revision_id` must match the project's current pointer; null means no prior active revision.
- `idempotency_key` identifies one save attempt and is unique within the owner/project. Retrying the same key with the same payload returns the original saved revision; reusing it with different content fails.
- Under a transaction and project lock, verify ownership and the parent/scan references, append the revision, update the active pointer and compatibility summary, and commit together.
- A stale precondition produces a conflict; do not overwrite another tab's work. Failed calculation or persistence leaves the previous active revision intact and the local draft retryable.
- The server/database derives the author from the authenticated session. Clients cannot select another owner or advance another project's pointer.

Rescanning or replacing a plan creates a new asset/scan revision. Keep the old revision and require review before reapplying old quantity corrections. Reopening a saved result uses its captured prices; an explicit price refresh creates another revision. Reset similarly creates a new saved revision when committed, preserving previous corrected history.

The browser continues to persist to Supabase while FastAPI computes. A transactional Supabase function can implement the save contract. If FastAPI later loads project data through a service-role client, it must verify project ownership explicitly. Current authentication alone does not authorize an arbitrary project ID. No new persistence endpoint, migration or access policy is enabled in item 1.

## Verification commands

```powershell
# Repository root
npm run typecheck
npm run build

# backend/
./.venv/Scripts/python.exe -m pytest -m "not ocr" -q
./.venv/Scripts/python.exe -m pytest tests/test_api_estimate.py::test_real_plan_image_prices_end_to_end -q
```

The focused image contract tests exercise floor, electrical and plumbing input retention without invoking OCR. Existing electrical/plumbing API tests remain in the non-OCR regression suite. The real floor-plan test verifies that the additive response works with materialized extraction/frame data.
