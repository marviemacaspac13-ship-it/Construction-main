# Gemini electrical request repair — 27 October 2026

## Confirmed causes

The existing key successfully listed models. Listing a name did not establish
generation access: one bounded request to `gemini-2.5-flash-lite` returned 404
`NOT_FOUND` with the specific explanation that this model was no longer available
to new users, recommending `gemini-3.5-flash-lite`.

The previous 20-second generation deadline was too short for the observed
responses. A diagnostic `gemini-2.5-flash` request with thinking disabled completed
in 30.267 seconds with HTTP 200. Its 65 proposals included many questionable
devices; this is not an accuracy success and disabling thinking was not shipped.

The recommended `gemini-3.5-flash-lite`, with the production prompt/schema and
default thinking behavior, completed in 23.303 seconds with HTTP 200 and STOP:
nine light-point and six switch proposals. Free-tier input/output eligibility
was checked against [Google's pricing](https://ai.google.dev/gemini-api/docs/pricing).
No billing, credentials, provider account or paid-only models were changed.

## Shipped behavior

- Primary model: `gemini-3.5-flash-lite`; secondary: `gemini-2.5-flash`.
- The rejected `gemini-2.5-flash-lite` is no longer in the electrical allowlist.
  Unpinned `latest` aliases and paid-only models remain rejected.
- Per-model deadline: 60 seconds. Overall provider-stage deadline: 125 seconds,
  including bounded encoding. Maximum two attempts, one per configured model.
- Bad-request/auth/quota/oversize errors still stop further provider attempts.
  Automatic local fallback remains enabled, with no detector selector.
- Electrical transport now reads at most 1 MB on success or error. It retains a
  bounded error response internally so logs can distinguish a known model-access
  failure from a generic HTTP status. Only whitelisted categories, model name and
  elapsed time are logged; raw bodies, image data and credentials are not logged
  or returned to the UI.
- Updated local/example model order, setup documentation and standalone runner
  default. No pricing, review contract, constants or detection thresholds changed.

## Verification and limits

754 offline backend tests passed; 53 OCR tests deselected. Four new cases verify
the replacement/default allowlist, longer async deadline, safe error category and
oversized-error boundary. Existing provider success, local fallback, auth/quota
stop, receipt, review, pricing and saved-estimate tests remain passing.

Started the repaired backend and uploaded sheet 11 through the signed-in browser.
`POST /api/electrical/proposals` returned 200, and review displayed fifteen
proposals: nine lights and six switches. No manual devices were added in this new
review. Product selection/box confirmation remained required; confirmation stayed
disabled. The prior saved ₱3,191.76 estimate was not overwritten. The fresh review
was left open for inspection.

Several returned boxes are visibly misplaced. Matching the expected aggregate
counts does not establish location accuracy, and proposed gang/function fields
remain subject to review. The connection repair does not close R25 recognition
acceptance or establish low-manual-effort estimating across drawings.

Request budget used: one model-list GET, three diagnostic generation requests
(Flash, rejected old Flash-Lite, replacement Flash-Lite), and one live browser
scan. No automatic retries or additional model discovery loop were added.

Local evidence: `../tmp/gemini-model-availability-2026-10-27.json`,
`../tmp/gemini-repair-gemini-2.5-flash.json`,
`../tmp/gemini-repair-gemini-2.5-flash-lite.json`,
`../tmp/gemini-repair-gemini-3.5-flash-lite.json`, and
`../tmp/gemini-repair-2026-10-27/review.png` / `review.txt`.
