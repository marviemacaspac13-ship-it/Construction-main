
# TRACE

TRACE reads construction plan images and produces material estimates in Philippine pesos. A Vite frontend manages sign-in, projects and saved results through Supabase. A FastAPI service reads drawings and calculates estimates. The [backend guide](backend/README.md) describes setup and API behavior.

The three plan types use different readers: floor plans use printed dimensions; electrical review uses Gemini-first device proposals, light/outlet position refinement and automatic local-symbol fallback; plumbing supports optional reviewed Gemini WC/LAV proposals with configured fallbacks and the original printed-tag reader last. Provider configuration is managed by the backend. The calculation engine is deterministic. Users can review saved originals, correct supported source quantities and project prices, and reopen saved revisions. Recognition accuracy on unfamiliar drawings remains limited.

## Electrical device review

Electrical review groups devices by type and links the selection to highlighted
plan markers. Apply a product, compatible-box decision or exclusion reason to
selected devices; edit exceptions individually. Shared switch confirmation records
one-way function/gang count explicitly and flags conflicting specifications.
An undo action and final quantity/exclusion summary support checking decisions.

Supported lights/outlets receive established wire/conduit allowances. Reviewed
eligible switch/AC devices and confirmed boxes can be priced; switch/AC wiring,
breakers, panels and circuit design remain excluded. The latest grouped UI has
offline browser and signed-in save/reload/Projects reopen/CSV/price edit/reset evidence.
The live fixture used local fallback and a labelled synthetic switch, not new
model recognition. See [implementation](backend/ELECTRICAL_GROUPED_REVIEW_2026-10-27.md)
and [live acceptance](backend/ELECTRICAL_GROUPED_LIVE_ACCEPTANCE_2026-10-27.md).

## Plumbing fixture review

The image-based **Review plumbing fixtures** screen appears during a plumbing scan,
before estimating, when a configured model returns usable proposals. Create a
Plumbing Plan project and upload a drawing, or open an existing result and choose
**Replace / rescan plan**. Select, move, resize, add or remove fixture boxes, then
confirm the counts to generate the estimate. Model selection and fallback are
managed by the backend.

Saved Results show the accepted boxes; direct box editing requires a new scan.
Numeric quantity corrections remain available separately. See the
[review instructions and configuration](backend/PLUMBING_VISION_SETUP.md#where-to-find-the-fixture-review)
and the [live acceptance record](backend/PLUMBING_VISION_LIVE_ACCEPTANCE_2026-10-22.md).

## Local setup

Install frontend dependencies with `npm i`, then run `npm run dev`. Create `.env.local` with `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Start the Python API from `backend/` with `.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000`; it needs `backend/.env` and the database migrations described in the backend guide. Python 3.13 is required for the pinned backend dependencies.

The [27 October status matrix](docs/revisions/STATUS_2026-10-27.md) separates completed R27/R30–R32 scope from open recognition, workflow acceptance and product decisions. Use the [remaining-work plan](docs/superpowers/plans/2026-10-27-remaining-revisions.md) for next tasks, [accuracy/limitations summary](docs/revisions/ACCURACY_AND_LIMITATIONS_2026-10-27.md) for submission claims, and [todo.md](todo.md) for detailed history. The [client checklist](docs/revisions/REVISION_CHECKLIST.md) preserves the original request wording.

The [14 October handoff](HANDOFF_2026-10-14.md) is historical; the linked current status supersedes its next-work list.

## Verification

28 October electrical follow-up: saved-response audit and a conservative
ownership-aware alignment pass improved one exposed lighting replay from 13 to
14 matched locations out of 19; the other three saved outputs were unchanged.
58 focused tests and 785 non-OCR backend tests passed, with 53 OCR tests excluded.
No provider calls or pricing changes. See [evidence and limitations](backend/ELECTRICAL_ALIGNMENT_FOLLOWUP_2026-10-28.md).

A separate [28 October classification diagnostic](backend/ELECTRICAL_CLASSIFICATION_TRIAL_2026-10-28.md)
used one approved crop-board request. It recovered two target outlet families but
misclassified a known light. The crop method was not adopted; production types,
counts and prices remain unchanged.

A separately approved [reference-context follow-up](backend/datasets/electrical-context-2026-10-28/README.md)
also failed the light control and returned all supplied proposal boxes unchanged.
This approach remains experimental and has not been integrated.

The [local reference review pack](backend/datasets/electrical-reference-review-2026-10-28/README.md)
prepares a different development family for independent human checking: 21 draft
locations and one unresolved mark. It supplies no new recognition accuracy claim.
A separate original-only AI pass agrees on the 21 broad visual locations; its
reconciled ledger distinguishes receptacle-like glyphs and switch text from
certified device types/assemblies. Human completeness checking remains pending.

The [28 October owner-reviewed local baseline](backend/datasets/electrical-reviewed-baseline-2026-10-28/README.md)
found none of the 15 reviewed light/receptacle glyphs on sheets 04/07 and proposed
six false lights at dimension endpoints. Six S text marks were also absent from
the unsupported local switch path. This is local-fallback evidence on exposed
development data, not a new Gemini-first result; production is unchanged.

A separate approved [whole-drawing Gemini trial](backend/datasets/electrical-whole-sheet-2026-10-28/README.md)
on the same originals matched only 1/9 receptacle locations, 1/6 lights and 0/6 S
marks under the fixed 20-pixel class/location rule. The owner-excluded ring was
proposed as an outlet. Both primary and local recognition remain unreliable on
this exposed family; no production or pricing change followed the test.

Earlier recorded scope: the 27 October execution passed 776 non-OCR backend tests
with 53 OCR tests deselected, plus 46 frontend/storage tests and typecheck/build.
Grouped-review live persistence, CSV and price edit/reset passed with external
recognition disabled for the fixture. This is not the entire OCR suite or a
new-family recognition-accuracy certification.

The bounded checks on 25 October 2026 passed 661 non-OCR backend tests, 36 frontend/database tests, twelve electrical image regressions and six representative real-image API outcomes; TypeScript checking and the production build also passed. The full OCR suite was not run. See [results and limits](backend/SUBMISSION_ACCEPTANCE_2026-10-25.md). Subsequent [live correction/manual acceptance](backend/EDITOR_LIVE_ACCEPTANCE_2026-10-25.md) passed 29 API/database assertions and browser save/reopen/reset checks. Four backend dependency deprecation warnings and the large-bundle build advisory remain. These checks do not certify recognition accuracy on new drawing families.
