# Gemini-first electrical review with automatic local fallback

Implemented 26 October 2026 after the user requested Gemini electrical proposals
with local detection retained as fallback, not a user-selectable option.

## Flow and scope

Every Electrical Plan upload now enters the same reviewed **partial devices and
boxes** workflow. The upload screen has no detector/mode selector. The backend
tries configured Gemini models first, then uses the existing local matcher if
Gemini is disabled, unconfigured, busy, times out, exceeds quota, returns an
HTTP error, empty observations or invalid data. Provider success skips local
detection entirely. Inventories are never added together.

Gemini's prompt asks for lights, receptacles, switch assemblies, AC outlets and
uncertain devices, using adjacent labels and the drawing legend as evidence.
It excludes legend examples, schedules and text unrelated to installed devices.
Socket configuration, gang count and switching function remain separate; `S3w`
must not become a three-gang switch merely because it contains the digit three.

Both paths return editable boxes for explicit review. The review displays source,
nearby text, uncertainty and limitations. Gemini supplies neither catalog SKUs nor
prices, compatible box claims, wire sizes or circuit quantities. Existing product
and box confirmation guards remain. The local detector is unchanged and still
does not recognize switches automatically.

Successful provider provenance, attempts, returned model identity where present,
prompt version and limitations are signed into the owner/image-bound receipt,
then preserved in the saved review. Failed attempts are also retained when local
fallback produces the review. Old saved snapshots remain readable without a
migration. The legacy direct electrical estimating API is preserved, but it is
not a frontend alternative or an automatic scope-changing fallback.

## Local setup and request bounds

Updated 27 October: model order and deadlines below supersede the original
26 October configuration. See [request repair and live verification](ELECTRICAL_GEMINI_REPAIR_2026-10-27.md).

Later on 27 October, [position refinement](datasets/electrical-grounding-2026-10-27/README.md)
was added: the response may align light/outlet boxes to nearby unambiguous local
glyphs while the signed receipt retains original model boxes. No inventories are
combined, no devices are added and classes/counts/prices stay unchanged.

`backend/.env` now enables this user-authorized electrical integration, using the
existing Gemini key from the previously user-confirmed free-tier project:

```dotenv
ELECTRICAL_VISION_ENABLED=true
ELECTRICAL_GEMINI_MODELS=gemini-3.5-flash-lite,gemini-2.5-flash
```

The example environment defaults to disabled. The reviewed free-tier allowlist
now contains 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite, 3.1 Flash-Lite and 2.5 Flash;
the default remains the two model names above. See the [five-model comparison](datasets/electrical-model-comparison-2026-10-27/README.md).
No paid-only model,
OpenRouter, automatic model discovery, billing upgrade or credential change is
performed. Actual free usage depends on the API project's tier; model names do
not override a project's billing configuration. Eligibility was checked against
[Google's pricing](https://ai.google.dev/gemini-api/docs/pricing) and
[model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash).

There are at most two provider attempts, once per configured model, with a
60-second ceiling per attempt and a 125-second provider-stage deadline including
encoding. Encoding has a ten-second ceiling, concurrency is two and queue wait
is capped at two seconds. Bad-request/auth/oversize/quota statuses
400/401/403/413/429 immediately trigger local fallback without trying another
model. Other failures may try the next configured model before local fallback.
No same-model retry occurs within one upload. Response size, device count,
coordinates and text fields are bounded and validated. Error logs contain
status categories, not raw provider bodies, credentials or image payloads.

The Pydantic fixed coordinate tuple remains strict at our boundary. The provider
schema explicitly uses a four-number homogeneous array rather than Pydantic's
`prefixItems` representation, following Gemini's supported structured-output
array format. See [Google's structured-output documentation](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).

## Live trial: no accuracy result

The existing checked lighting sample `11.png` (683 x 658, SHA-256
`a0904d2fe20533391e6e0f516027fdae71585860a2880e1a6ef0061d8897e44c`)
was sent to `gemini-2.5-flash` in two separate, bounded trial invocations:

| Trial | Provider outcome | Provider elapsed | Interpretation |
| --- | --- | --- | --- |
| Initial request | HTTP 400 | 1.530 s | No detections. The raw rejection detail was not captured; inspection found a provider-schema tuple incompatibility, which was corrected. |
| One corrected trial | HTTP 503 | 11.700 s | No usable provider result. Does not establish accuracy, quota exhaustion or successful schema acceptance. |

Each invocation allowed exactly one request, with no automatic retries or local
inference. Sanitized records are in
`datasets/electrical-gemini-validation-2026-10-26/sheet-11.json` and
`sheet-11-corrected.json`. Receipts and credentials were not saved. No estimate or
project was written by the trial script. No further live provider calls followed.

Offline tests cover successful Gemini-to-reviewed-plan provenance, model order,
timeout/HTTP 503/local fallback, bad-request/auth/quota early exit, invalid and
empty output, semantic deduplication versus conflicts, unsupported switch types,
coordinate-schema compatibility and immutable receipt ownership. Successful
Gemini detection accuracy and broader drawing-style generalization remain
unverified. Full client revision acceptance is still open.

Final checks: **736 non-OCR backend tests passed** (53 deselected), **40 frontend/
storage checks passed**, TypeScript and production build passed. The existing
bundle-size advisory remains. The interface detector reported no findings.
The signed-in browser showed the updated upload explanation with no detector
selector; it was stopped before uploading/scanning again, so no further model
requests or database writes occurred. Screenshot:
`../tmp/electrical-gemini-2026-10-26/upload.png`.

Subsequent user-approved live UI test: Flash timed out and Flash-Lite returned
404, followed automatically by nine local light proposals. Review/save/reload/
reopen/export passed at an explicitly partial P198; Gemini accuracy remains
unverified. See [the live test report](ELECTRICAL_GEMINI_LIVE_TEST_2026-10-26.md).
