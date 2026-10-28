# Estimate revision storage: deployment and verification

Task 2 completed, 10 October 2026. The user confirmed a CSV export and applied migrations 003 and 004. Live signed-in browser scan/save/reopen and reciprocal two-user acceptance passed. The backend feature is enabled.

## Live acceptance evidence

The existing signed-in browser account created `ACCEPTANCE 2026-10-10 LIVE`, uploaded `backend/tests/fixtures/plans/01.png`, scanned and saved, returned to Projects, reopened the result, and reloaded the page. The result remained ₱309,364.97, eight material types and 91.90 m wall length. The acceptance project is retained for review. Screenshot: `tmp/acceptance/reopened-result.png`.

The local test login differed from the browser account. API checks used that login plus a temporary confirmed, unprivileged account. All isolation requests used genuine user JWTs and the anonymous application key. Administrative credentials were used only for test-user creation/cleanup and the existing backend save RPC, not as evidence of RLS isolation. No email was sent.

70 live assertions passed: authenticated OCR and save; exact stored response, original/effective inputs, full estimate including `unpriced`, extraction and unsupported detections; checksum/size metadata; reciprocal owner reads and foreign empty reads across projects/assets/scans/estimates; foreign backend save 404; foreign rename/delete affecting zero rows; direct authenticated RPC/history mutation denial; identical-key retries; changed-content key conflicts; revision advancement; older retries without pointer rewind; failed-scan result preservation; stale HTTP 409 in both sessions; no duplicate revisions; and cleanup. All three disposable API projects and the temporary auth user were removed. Existing projects were not modified. [Sanitized results](LIVE_ACCEPTANCE_2026-10-10.json).

Live testing found a stale-save defect: the original `40001` rejection repeatedly timed out at the 60-second client limit; a direct RPC probe also timed out at 15 seconds. No stale write advanced the pointer. Migration 004 changes that application precondition failure to `PT409`, explicitly returning HTTP 409 through PostgREST. The precise infrastructure timeout mechanism was not established. The user applied 004, and a full acceptance rerun passed, including both stale-save cases. Locking, owner checks, idempotency and transaction semantics are unchanged. FastAPI accepts both error codes during rollout.

The isolated tests apply 003 then 004 and assert the `PT409` SQLSTATE: 17 checks pass. Focused backend revision tests after the fix: 18 passed. This evidence exercises Floor Plan in the browser and real OCR through FastAPI; it does not certify electrical/plumbing recognition accuracy, simultaneous lock contention, or original-image storage. Empty unresolved lists establish round-trip retention on this fixture; nonempty unresolved-item preservation and transaction rollback are covered in isolated tests.

To repeat with explicit authorization for live test writes:

```powershell
cd backend
./.venv/Scripts/python.exe scripts/live_revision_acceptance.py --run-live
```

The script reads the ignored local test credentials and never prints passwords, keys or tokens. `--skip-known-stale-check` was used only to finish unaffected checks while diagnosing the original timeout; do not use it for acceptance. The final report was generated without that omission.

## What is implemented

- Immutable asset metadata, scan revisions and estimate revisions, with a project active-revision pointer. Original image bytes/private storage are task 4; `storage_path` is currently null.
- Complete source plan, resolved parameters, version identifiers, catalog price snapshot/capture time, extraction, unsupported detections, full priced and unpriced BOM, assumptions and pricing time.
- Transactional scan saves with a project lock, expected prior revision, same-payload idempotent retries, parent links and compatibility summary updates.
- Owner-only browser reads; no browser writes to history, result summaries or the active pointer. FastAPI calls the service-only RPC with the authenticated owner and verifies deterministic computation before writing.
- Save retry without rerunning recognition. The exact pending payload/key remains in memory while the scanning screen stays open. Closing, refreshing or navigating away discards that unsaved draft; no durable offline draft is claimed.
- Legacy rows remain readable without fabricated inputs. Their results screen explains that a new upload/scan is required before corrections.

This endpoint stores initial scans/rescans only. Quantity/price correction execution, revision selection/history UI, private file upload and plan viewing remain later TODO tasks. Recorded prices are project-local data, not an authenticated certification of the shared catalog. Replay verifies arithmetic against the captured input; it does not prove OCR accuracy or possession of the source image.

## Deploy in order

1. Back up the database and test on a staging Supabase project first. Confirm migrations `001_project_extraction.sql` and `002_project_owner.sql` are already applied, `projects.id` and `user_id` are UUIDs, and owner policies match migration 002. No existing rows are backfilled with invented source inputs.
2. Keep `ESTIMATE_REVISIONS_ENABLED=false` on the backend. Coordinate the frontend/backend rollout: migration 003 removes direct browser result/status writes, so an old frontend cannot complete scans afterward. Pause new scans during the deployment window while existing results remain readable.
3. Run `003_estimate_revisions.sql` once, as a single transaction, in the staging SQL editor with its normal administrative role. It is deliberately not a silent rerunnable migration: duplicate objects signal that its deployment state needs inspection.
   Then run `004_revision_conflict_response.sql` to install the explicit stale-save conflict response. Do not rerun 003 on an already migrated database.
4. Verify policies, function privileges and table grants with the queries below. The browser must have SELECT only on the new tables. The save/failure functions must be executable by `service_role`, not `anon`, `authenticated` or PUBLIC. Service-role callers have no direct privileges on the new tables; the SECURITY DEFINER functions own the writes and explicitly check project ownership.
5. Deploy the matching backend and frontend. Set `ESTIMATE_REVISIONS_ENABLED=true` only after the staging checks pass, then restart the backend. This is a backend-only environment variable; never expose the service-role key in Vite.
6. Test with two genuine staging user sessions via the browser/PostgREST, not only the administrative SQL editor. An SQL-editor session normally bypasses RLS. Complete the acceptance checks below before repeating the migration/rollout on the live project.

Missing storage/migrations produce an actionable save error with a retry path; there is no fallback that silently drops source inputs or unpriced lines. The existing scanning flow can still compute while persistence is disabled, but cannot complete its save. Do not release that mixed configuration to users.

```sql
SELECT tablename, policyname, cmd FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('projects','plan_assets','scan_revisions','estimate_revisions');

SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND table_name IN ('plan_assets','scan_revisions','estimate_revisions');

SELECT grantee, column_name, privilege_type FROM information_schema.column_privileges
WHERE table_schema = 'public' AND table_name = 'projects'
  AND grantee IN ('anon','authenticated');

SELECT has_function_privilege('authenticated',
  'public.save_scan_estimate(uuid,uuid,uuid,uuid,jsonb,jsonb)', 'EXECUTE') AS browser_can_save,
  has_function_privilege('service_role',
  'public.save_scan_estimate(uuid,uuid,uuid,uuid,jsonb,jsonb)', 'EXECUTE') AS backend_can_save;
-- Expected: false, true.
```

## Staging acceptance

- User A creates/scans a project; reopen it and compare the full stored input, catalog snapshot, `estimate.unpriced` and unsupported detections with the API response. All three plan types use this contract.
- User B cannot select A's project/assets/scans/revisions, call the save RPC directly, or save to A's project through FastAPI. The API returns the same not-found response for missing and foreign projects.
- Two tabs start from the same pointer. Save one, then save the other: the latter receives HTTP 409 and cannot advance the pointer. No automatic rebase occurs.
- Simulate a committed save whose response is lost. Retry with the same payload/key: the same revision returns and no duplicate asset/scan/revision is created. A retry of an older committed save never moves the pointer backward.
- Reuse a key with changed content: conflict. Fail partway through a save: all inserts and summary updates roll back.
- Failed recalculation/save/rescan leaves the old active result intact. A failed scan also preserves a completed legacy result.
- Rename/create/delete operations work with the restricted grants. Owner deletion of a project removes its metadata/history by cascade; image-object cleanup belongs to task 4.
- Inspect a pre-migration project: its summary still renders, with a re-upload/rescan explanation. No editable baseline is reconstructed from material lines.

The isolated tests cover these SQL invariants using simulated auth roles and the actual migration. They do not substitute for real Supabase JWT/PostgREST/schema-cache verification. PGlite serialises connections; tests exercise stale preconditions, not a multi-connection lock-contention benchmark.

## Verification commands and results

```powershell
npm run test:revisions
npm run typecheck
npm run build
cd backend
./.venv/Scripts/python.exe -m pytest -m "not ocr" -q
```

Verified: 17 isolated database/browser-save helper checks; 433 non-OCR backend tests (49 OCR tests deselected); TypeScript and production build pass. The build retains its existing large-bundle warning. Existing backend dependency deprecation warnings remain. Recognition and takeoff formulas were unchanged, so the OCR suite was not rerun for task 2.

UI UX Pro Max's error-recovery guidance was applied to the existing scanning screen. A temporary browser harness with mocked application requests verified the actual screen in React StrictMode: initial save failure, retained result, disabled controls during retry and successful navigation afterward. The 375 px viewport had no horizontal overflow; both recovery buttons measured 44 px high. The default desktop viewport was visually inspected too. The harness made no database writes and was removed afterward. Physical devices, landscape and enlarged system text remain unverified. Live authenticated acceptance is documented above.

If rollout fails, disable revision saves and pause new scans while investigating; preserve the new history tables and existing data. Do not drop tables or restore direct legacy result writes as an improvised rollback. Restore from the tested backup only through an explicit recovery procedure.

