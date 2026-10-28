# Reviewed plumbing: live acceptance, 22 October 2026

The signed-in application completed a real image proposal, visual confirmation,
estimate, database save, Projects reopen and full page reload. Gemini 3.8 Flash
proposed two water closets and two lavatories on the cafeteria sample; all four
were accepted after visual review. Six material lines totalled **₱4,300**.
The reopened page retained the original image, both counts and all four boxes.

Project: `ACCEPTANCE — Gemini plumbing — 2026-10-22`
(`badee6c4-e7ec-436e-a62b-6ca2afdc931b`), scan revision prefix `c2477e8c`.
The test project remains available for inspection. Retries reused this project;
unrelated projects were not modified.

## Failures resolved during the test

Initial requests encountered provider availability failures and a structured-output
schema rejection: large nested array bounds exceeded Google's schema-state budget.
The provider schema now omits those large array limits; local response validation
still enforces 500 fixtures and 30 limitations. Coordinate bounds remain enforced.
Gemini 2.5 Flash was added as an early configured fallback; its schema request was
checked using text only. The successful image request used primary Gemini 3.8 Flash.

The original OCR fallback read only one WC and correctly refused that sparse result
with 422. No detector minimum was lowered. Sanitized provider failure categories
are logged without upstream bodies or credentials. Frontend retry clears the old
reader caption; both upload entry points disclose external image processing.

## Evidence and scope

- [Audit-derived acceptance record](datasets/gemini-fixture-trial-2026-10-17/LIVE_ACCEPTANCE_2026-10-22.json)
- [Rendered-page checks after reload](datasets/gemini-fixture-trial-2026-10-17/live-browser-checks.json)
- [Review screenshot](../tmp/acceptance/plumbing-live-review.png)
- [Saved and reloaded result](../tmp/acceptance/plumbing-live-reopened.png)
- [Configuration and behavior](PLUMBING_VISION_SETUP.md)

Source: `tests/fixtures/plans/Data Set/Plumbingplan/IMAGE/01.png`, 1356 × 650.
This is one previously exposed drawing, reviewed by the same assistant conducting
the test. It establishes the integration flow, not independent accuracy or broad
drawing-style coverage. No live OpenRouter image request, successful alternate-model
image request or cross-user browser acceptance was performed. Pipe lengths remain
rule-derived allowances, not measured routes. Provider quota and availability remain
external constraints.

Final regression checks: 641 non-OCR backend tests passed (53 OCR tests excluded),
four frontend geometry/validation tests passed, TypeScript checking and the
production build passed. The build retains its existing large-bundle advisory.
