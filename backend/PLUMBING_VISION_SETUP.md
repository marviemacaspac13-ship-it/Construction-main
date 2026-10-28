# Reviewed plumbing proposals and model fallback

Implemented 22 October 2026. This extends plumbing only; floor-plan and electrical
recognition and the deterministic material rules retain their existing paths.

Live acceptance passed on the cafeteria sample: Gemini 3.8 Flash, two WC and two
LAV, ₱4,300, saved and reopened with boxes intact after a full reload. See the
[live acceptance record](PLUMBING_VISION_LIVE_ACCEPTANCE_2026-10-22.md) for evidence
and the limits of this single-drawing test.

## Before and after

| Before | After, when enabled |
| --- | --- |
| Plumbing reads printed OCR tags | Gemini proposes visible WC/LAV bodies, including untagged ones |
| Scan proceeds to estimate/save | User reviews boxes, removes/relabels/adds fixtures, then explicitly confirms |
| Unreadable tags can refuse a drawing | Configured alternative image models run in order; the final fallback is the original reader |
| Saved evidence contains OCR centers | Saved scan input also contains proposed and accepted boxes, model, attempts, image hash, dimensions and confirmation time |

The fallback sequence is not a vote or a union of counts. It stops at the first
nonempty structurally valid proposal. Review is still necessary because schema
validation cannot detect missed fixtures or a confidently incorrect classification.

## Configuration

Use `backend/.env`; do not put credentials in frontend environment files.

```dotenv
PLUMBING_VISION_ENABLED=true
GEMINI_API_KEY=your-key
PLUMBING_GEMINI_MODELS=gemini-3.8-flash,gemini-2.5-flash,gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-2.5-flash-lite
OPENROUTER_API_KEY=
PLUMBING_OPENROUTER_MODELS=
PLUMBING_REVIEW_SECRET=your-shared-random-secret
```

The model identifiers above were checked against Google's model catalog during
implementation. Availability and free-tier access depend on the account and may
change; this implementation does not guarantee that every configured model is free.
Only configured models with a corresponding provider key are attempted. Add explicit
vision-capable OpenRouter IDs in comma-separated order for further fallbacks.
There is no arbitrary provider discovery or automatic free-model router, and no
local SAM/CountGD installation. At most eight distinct configured models are used.

Restart the backend after changing settings. The feature is disabled by default
in `.env.example`; without keys, it goes directly to the original reader. A shared
random review secret is required for multiple workers or review continuity across
restarts; otherwise a per-process secret is used. Do not disclose this secret.

No additional package or database migration is required. `httpx` is already pinned.
Evidence is stored inside the existing JSON scan input and revision save contracts.

## Where to find the fixture review

**Review plumbing fixtures** appears during a plumbing scan, after a model returns
proposals and before the material estimate is calculated. It is not a separate
page in Projects or an editor on the saved Results screen.

For a new project, choose **Plumbing Plan**, upload the drawing and start the scan.
For an existing estimate, open its Results page, choose **Replace / rescan plan**,
confirm the replacement prompt, then upload and scan the plumbing drawing again.
The current saved version is retained; previous corrections do not carry forward
into the new scan.

On the review screen:

1. Click a fixture box to select it. Drag the box to move it or a corner to resize it.
2. Use **Add fixture** to place or draw missing boxes. Select the fixture type,
   change incorrect types, or remove false detections.
3. Check the entire drawing, tick the explicit count-confirmation checkbox, then
   choose **Confirm counts and estimate**.

The saved Results page displays the accepted boxes on the original plan. Its source
quantity editor changes numeric quantities separately; it does not reopen or alter
the scan-time boxes. To perform direct box editing again, start a replacement scan.

The review screen appears only when cloud proposals are enabled and a configured
model returns usable proposals. If the backend exhausts its model sequence and
selects the original OCR reader, there is no model-proposal box-review step.
The screenshot headed “Development preview” shows the isolated demonstration;
the same review component is integrated into the real scan flow.

## User flow and guarantees

1. The normal upload flow saves the private original and checks its identity.
2. `POST /api/plumbing/proposals` tries configured Gemini models, then configured
   OpenRouter models. Timeouts, provider errors, blocked/truncated/malformed output,
   invalid coordinates and empty proposals advance to the next model. Responses
   and inference work are bounded; there are no retry loops on the same model.
3. Proposals appear on the uploaded image with zoom/scroll. Users can select a
   numbered fixture directly on the image, relabel or remove it, click to place
   a box or drag to draw one. Dragging a box moves it; corner handles resize it.
   Arrow keys move focused boxes and Shift + arrows resize them. No numeric
   coordinate fields are exposed. Edits reset confirmation. Same-class near-duplicates
   are suppressed; overlapping conflicting classes remain reviewable and cannot
   be confirmed until resolved. Similarity/confidence is not a probability.
4. Model selection and fallback belong exclusively to backend configuration.
   The frontend has no model-switch or reader-switch controls, and the proposal
   endpoint accepts only the uploaded file, not a requested model or continuation.
   Exhausted automatic model calls select the original reader as the final fallback.
5. Confirmation sends the accepted instances and a signed receipt to the existing
   `POST /api/estimate/image`. Receipts bind image hash, user, dimensions, model
   provenance and original proposals, expire after four hours, and cannot be
   applied to another image or user.
6. Confirmed WC/LAV counts replace the corresponding OCR quantities, including
   explicitly excluded classes. Other supported plumbing tags are retained.
   The engine derives pipe/fitting allowances; visual recognition does not measure
   pipe routes or price fixtures themselves.
7. The original automatic reader keeps its existing minimum-fixture guard. An
   explicitly reviewed small WC/LAV layout can be estimated below that automatic
   floor; a plan with no material-bearing fixtures is still refused. No unreviewed
   AI proposal is used to bypass the original reader's guards.
8. Existing save/reopen and correction workflows retain the scan evidence. The
   results viewer shows accepted scan boxes; later numeric corrections are separate
   records and do not rewrite the original boxes.

Cloud proposals send image pixels to configured external providers. The upload UI
states this; provider keys and upstream error bodies are never exposed. Rotated-EXIF
images fall back to OCR; export an upright raster for correct visual-review axes.
Full-sheet images are re-encoded without metadata and capped at 4096 pixels per
axis with their aspect ratio preserved. Small symbols may still be missed.

## Verification and limitations

Offline tests mock model responses. They cover ordered backend fallback, refusal
to let clients choose the next model, provider HTTP payloads, truncated/oversized responses, invalid and empty
results, duplicate/conflicting boxes, strict confirmation, owner/image/expiry
binding, count replacement, unchanged unrelated tags, small-plan confirmation,
original refusals, snapshot replay and immutable save/reopen data.

Verification on 22 October: 641 non-OCR backend tests passed (53 OCR tests
deselected), including 23 proposal/provider/review checks; four frontend review
validation checks passed; TypeScript checking and the production build passed.
The build retains its large-bundle advisory. The Impeccable mechanical check found
no findings in the changed review/upload/viewer targets.

The two user-supplied Gemini responses are development examples; see
[the trial record](GEMINI_FIXTURE_TRIAL_2026-10-17.md). Subsequent live acceptance
verified one Gemini image request and real save/reopen. Broader accuracy, alternative
providers, quota and latency are not established by that test.
Subsequent browser check: the preview is reachable at `http://localhost:5173/`
(the `127.0.0.1` browser connection had failed). Using the preserved cafeteria
response, the real review component was checked for removal, relabeling, image
click placement, drawing, selection, movement, corner resizing, reset, zoom/fit
and explicit confirmation. Coordinate-based controls were removed at the user's
request, along with all frontend detection-method controls. A startup
image error that incorrectly kept confirmation disabled was fixed and verified.
This isolated preview makes no live provider request and saves no project. The
main application's subsequent signed-in acceptance is documented above.

After the direct-image-editing revision, 50 focused backend proposal/authentication
checks, four frontend geometry/validation checks, TypeScript and the production
build passed. Browser inspection confirmed no detection-switch buttons or numeric
coordinate inputs remain. Placement, drawing, selection, movement and resizing
were exercised on the preview, and edits reset explicit count confirmation.

References: [Gemini model catalog](https://ai.google.dev/gemini-api/docs/models),
[GenerateContent API](https://ai.google.dev/api/generate-content),
[OpenRouter request schema](https://github.com/OpenRouterTeam/docs/blob/main/api_reference/overview.mdx).
