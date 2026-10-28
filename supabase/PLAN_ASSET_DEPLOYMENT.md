# Private original plans — task 4 / R32

Implementation date: 11 October 2026. Migration 005 was applied successfully and the local backend feature enabled. Live acceptance results are recorded in [the acceptance report](PLAN_ASSET_LIVE_ACCEPTANCE_2026-10-11.json); consult its status before treating acceptance as complete.

## Deployment

1. Keep `PLAN_ASSETS_ENABLED=false` until deployment finishes. Existing saved estimates remain readable. New UI scans require original-plan storage and offer retry when it is unavailable.
2. After migrations 001–004, run [005_private_plan_assets.sql](migrations/005_private_plan_assets.sql) once in the configured Supabase project's SQL editor. It creates the private `trace-plans` bucket, adds upload/cleanup bookkeeping, owner-checked service-only RPCs, and links new scan revisions to the uploaded asset. It retains historical metadata-only records and the CAS/idempotency save contract.
3. Confirm the bucket is private, has a 25 MB object limit and PNG/JPEG/WebP MIME allowlist. No browser role can directly read or write this bucket; a restrictive policy also constrains existing broad `storage.objects` policies. The backend issues five-minute signed viewing links after checking project ownership. A copied signed URL remains usable until it expires; it is a temporary bearer capability.
4. Set `PLAN_ASSETS_ENABLED=true` in `backend/.env`, retain `ESTIMATE_REVISIONS_ENABLED=true`, and restart the backend. Dependencies now explicitly pin Pillow 12.3.0 for format/dimension/decode validation.
5. Run the live acceptance below before marking task 4 complete. No database deployment or backend flag change is implied by the isolated tests.

## Behavior and lifecycle

- Upload original bytes before recognition. MIME must match decoded PNG/JPEG/WebP, the file must be non-empty and no larger than 25 MB, and the static image must contain at most 40 million pixels. PDF and animated images are rejected. Both creation interfaces show the supported image formats.
- Direct `/api/scan` and `/api/estimate/image` uploads now use those same checks before recognition. Their reads stop at 25 MB plus one byte; malformed or mislabeled images cannot enter OCR or symbol matching. This also applies when original-plan storage is disabled.
- Suggested creation-flow guidance for the coworker: “Upload the original PNG, JPG or WebP export, up to 25 MB. Keep the full drawing, printed dimensions, room labels and symbol labels visible. If the marks are hard to read at their original size, obtain a clearer export; enlarging a small screenshot does not restore missing detail.” Explain rejection using the API's specific size, format or corrupt-image message. This is advice, not an automatic quality threshold: the local comparison measured substantial recognition loss after downsampling, but provides no defensible minimum pixel count for all plan types.
- Upload IDs are stable across retries. Paths are generated from checked owner/project/upload UUIDs. Storage upload never overwrites; a lost-response retry compares stored bytes by SHA-256 before finalizing. Filenames are metadata, never path components.
- The immutable asset records checksum, original filename, MIME, byte size, dimensions and storage path. Scan/estimate revisions reference its exact ID. Opening a saved estimate does not choose a newer upload. Failed first scans have no estimate revision; Results opens the latest retained original for that attempt.
- Original-plan view controls support 1–8× fit-relative zoom, pointer/touch drag, fit, and keyboard `+`, `-`, arrows and `Home`. Links renew one minute before expiry; image/link failures have retry. Legacy metadata-only scans explain that the image is unavailable.
- Ready originals, including refused scans and previous versions, are retained provisionally. No automatic deletion of historical versions is introduced. Confirm final retention policy with the client.
- Incomplete uploads become cleanup candidates after 24 hours. Project deletion queues its private objects for cleanup after a 24-hour grace period, allowing in-flight uploads to settle. Signed links expire after five minutes. Browser cleanup is owner scoped and runs before uploads and after project deletion. Storage errors leave the queue intact for retry.
- For owners who do not return, run `.venv/Scripts/python.exe scripts/cleanup_plan_files.py` from `backend/` periodically using the service environment. Each run handles up to 100 files per owner; rerun to drain larger queues. This script never claims a ready original or linked scan version. No recurring job has been configured automatically.

## Verification before deployment

- `npm run test:plan-assets`: isolated PostgreSQL migration, restrictive storage policy, two-owner reads/writes, stable upload IDs, immutable scan linkage, lost-save retry, refused-scan preservation, stale-upload cleanup and project-deletion queue.
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_plan_assets.py -q`: original-byte preservation, PNG/JPEG/WebP validation, byte/pixel limits, ownership refusal before storage access, upload-response loss, conflicting object refusal, regenerated five-minute viewing links, legacy handling and cleanup retry.
- Existing backend non-OCR suite, frontend revision tests, type checking and production build.
- `tmp/acceptance/plan-viewer.html` is an isolated browser harness with explicitly simulated link responses and the real `01.png` fixture. Its screenshots are component evidence, not a claim of deployed storage acceptance.
- `backend/scripts/live_plan_acceptance.py --run-live` exercises deployed storage, real OCR/save/reopen, two accounts, refused scans and actual five-minute expiry. It requires authorization for temporary accounts, fixture uploads and cleanup, retains one named review project, and never logs credentials or signed URLs. `--reuse-review-project` reuses the project from its report when repeating a run.

## Live acceptance after migration

1. User A: scan `01.png`; confirm its original uploads before OCR, save, reopen from Projects and reload. Compare the displayed image, source checksum, scan asset ID and active estimate revision.
2. Exercise zoom, drag, keyboard pan, fit and mobile controls. Leave the screen open past link renewal; force a link failure, then retry. Verify an actually expired old signed URL is refused and a newly authorized URL succeeds.
3. Refuse an unreadable supported image; reopen its error project and confirm the original remains viewable. A failed rescan of an already completed project must preserve the previous estimate and its original.
4. User B: try A's project/asset IDs at upload and view endpoints. Expect 404; owner-scoped table reads return no A rows; direct browser Storage reads/writes are refused. Do not test isolation using an unexpired signed URL, which intentionally conveys temporary access.
5. Simulate interrupted upload and save responses; retry without duplicate asset/estimate records or overwriting bytes. Verify a second upload never changes the image under the earlier saved scan.
6. On explicitly disposable projects, verify deletion queues files, grace-period cleanup removes only eligible paths, and failed cleanup can be retried. Confirm legacy projects still open without fabricating their original file.

Coordination: this is the single R32 viewer, shared with the section 1 viewer requirement. It consumes the same `getProject()` active revision as the material table, summary and CSV export. Coworker PDF export should use that same snapshot. Coworker confirmation of the shared viewer and image-only upload contract remains outstanding; no external message has been sent.
