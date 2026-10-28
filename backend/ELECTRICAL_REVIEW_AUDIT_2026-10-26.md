# R25 electrical review: type and rule audit — 26 October 2026

The review-assisted direction is feasible, but electrical pricing cannot safely
reuse the plumbing implementation unchanged. The existing engine already accepts
switch and AC-outlet SKUs and assigns them convenience-outlet wiring allowances.
Adding recognition alone would expose that calculation gap. This audit changes
no production code, catalog data, templates, thresholds or model configuration.

## Evidence inspected

- Existing electrical rules, constants, parameters, units, source schema,
  correction contract and frontend source-field whitelist.
- [Supplied-reference contact sheet](reference_candidates/2026-10-11/contact-sheet.png),
  visually inspected, and its provenance manifest. These are existing faithful
  crops, not newly read PDF pages. The supplied appendix's edition remains unverified.
- [Existing symbol dictionary](datasets/electrical-audit/SYMBOL_DICTIONARY_2026-10-14.md)
  and draft mappings; no authoritative GS/SW product distinction was found there.
- [Machine-readable audit](datasets/electrical-review-audit-2026-10-26/audit.json):
  27 electrical entries from the committed catalog, source hash and seven
  single-assembly rule probes. No live catalog or external model was queried.
- Existing electrical-rule and source-correction tests: **64 passed**, two
  dependency deprecation warnings, 3.70 seconds. Windows TestClient initialization
  stalled in the sandbox; the same bounded offline tests passed outside it.

Passing these tests establishes current behavior, not the engineering validity of
all accepted catalog combinations. No new electrical-code compliance claim is made.

## Supported types versus available products

| Device family | Catalog entries | Present image/review support | Required treatment |
| --- | --- | --- | --- |
| Ceiling light point | CLR01–03, ceiling receptacles with different listed sizes | Matcher labels supported light symbols CLR01; frontend permits all three by manual choice | Keep CLR01 as existing library default. A fixture's visual style does not establish receptacle size or light-fixture purchase price |
| Convenience outlet | OT01–03, named 1/2/3-gang outlet | Matcher emits OT01 for the owner-selected duplex default; editor permits all three | Preserve that default and its provenance. Socket strokes do not automatically select gang count |
| One-way switch | SW01–03, named 1/2/3-gang 1-way switch | Contract accepts them; image path and frontend editor do not expose supported switch classification | A user-selected specified product can identify a SKU, but drawing-code interpretation, assembly count and switch wiring still need explicit rules |
| Generic gang switch | GS01–03, named 1/2/3-gang switch | Contract accepts them; no approved GS-versus-SW interpretation | Keep separate from SW. Do not silently alias or price both for one assembly |
| Three-way switch | No explicitly named three-way SKU in the captured catalog | Supplied S3w crop is identified as a three-way switch reference; actual plan notation remains drawing-specific | Preserve recognized semantic type as unresolved for pricing. Never map S3w to SW03, which is named a 3-gang 1-way set |
| AC outlet | ACO01, named 1-gang AC outlet | AC/ACU relabeller exists but READ_SYMBOL_LABELS is false | Separate AC service from convenience allowances before new reviewed support. Outlet appearance alone does not establish load, wire size or route |
| Panels/breakers | PB01, CBR01–05 | Catalog/rule inputs exist; no reviewed panel schedule parser | Keep outside this switch/outlet recognition milestone |

The supplied S, S2 and S3 crops are labelled single-pole, duplex and triplex in
the recorded reference extraction. That does not by itself identify a catalog
assembly or prove what every draughtsman's suffix means. The seven source
observations to retain separately are visual mark, adjacent text, semantic class,
socket configuration, gang count, switching function and catalog SKU.

## Calculation gaps reproduced locally

With default parameters, no measured runs and one fixture record:

| Input | Raw downstream output, excluding the input device itself |
| --- | --- |
| OT01 or OT02 | One UTB01, 22 m ELW04 and 6.6 m FPVC01 |
| CLR01 | One JCB01, 12.87 m ELW05 and 3.96 m FPVC01 |
| GS02, SW01, SW03 or ACO01 | One UTB01, 22 m ELW04 and 6.6 m FPVC01, exactly like an ordinary outlet |

These are observed engine outputs after waste but before purchase rounding,
not approved new switch/AC allowances. The wiring-device set currently mixes
all GS/SW/OT/ACO products. Its count path puts every member into the convenience
group; measured runs distinguish lighting, convenience and aircon services.

Required separations:

1. **Purchase assembly versus mechanism.** A two-gang product sold per set is not
   automatically two priced sets. Several mechanisms can share one assembly/box.
2. **Assembly versus mounting box.** Count a physical mounting location once;
   do not add a box for each semantic subcomponent. UTB01 alone does not specify
   all needed box sizes/configurations; verify product applicability.
3. **Lighting points versus switch legs.** Do not add a full convenience circuit
   allowance per switch. Explicitly define what the lighting allowance covers and
   prevent overlap with separate switch-leg quantities.
4. **AC versus convenience circuit.** ACO01 must not silently reuse the ordinary
   outlet wire group when its load/service is unresolved.
5. **Measured versus inferred routes.** Any nonempty `plan.runs` currently suppresses
   all count-derived wire/conduit globally. Preserve exclusivity; partial measured
   coverage needs a separately defined policy, not a mix that silently omits or
   double-counts devices. Do not infer cable routes from drawn control arcs.

Existing parameter comments cite references for parts of the allowance rationale;
they are not worked switch/multi-way/AC bills or a validated GS/SW product list.
Those remain explicit rule/product decisions, not conclusions this audit can invent.

## Proposed review contract checkpoint

Implement the data boundary first, with mocked proposals, before selecting a
recognizer or exposing new priced types:

- Separate electrical observations from catalog fixtures. Each observation retains
  a stable ID, normalized box, raw printed mark, proposed semantic class, nullable
  gang/socket/function attributes, uncertainty, assembly identity and mapping basis.
  Unknown is not zero and a proposed interpretation is not a confirmed product.
- Retain original proposals and accepted observations separately. Counts are
  derived from accepted instances/assemblies, never added to the matcher's aggregate.
  Switch text can be an independent candidate, not only a label near an outlet.
- Use server-validated electrical classes and product eligibility. A model must
  not supply authoritative SKUs, engineering allowances, prices or extra routes.
- Bind confirmation to owner, image hash/dimensions and expiry, as in plumbing.
  Reject duplicates/conflicting overlapping observations and stale/wrong-image
  receipts. Preserve provenance and immutable revision replay.
- Distinguish supported/priced, unclassified, explicitly excluded and recognized
  but unsupported observations. Keep an auditable unresolved list. A sheet with
  unresolved material-bearing devices must not look like a complete priced takeoff;
  decide whether to block completion or require explicit partial-estimate acceptance.
- Add a dedicated electrical evidence field/type. Plumbing's `FixtureReview` is
  WC/LAV-specific in Python and TypeScript, and the estimator changes its audit
  wording whenever that field is present. Reusing it unchanged would mislabel
  electrical provenance. Inspect JSON revision validation for additive compatibility;
  do not assume a database migration is necessary or unnecessary before checking.

This checkpoint would retain the current supported CLR01/OT01 behavior and record
unresolved switches/AC separately. It would not claim R25 complete or publish
new switch prices. New SKU/allowance support follows the explicit rule decisions.

## Subsequent checkpoints

After the user confirms the contract checkpoint:

1. Approve the supported product/mapping list and worked rules, then implement
   isolated purchase/box/service groups with exact quantity tests.
2. Connect the review UI using the established plumbing interaction pattern,
   preserving the coworker's frontend ownership and the existing visual language.
3. Evaluate an electrical proposer on explicit reviewed samples. Keep the user's
   free-tier-only requirement. Recent plumbing timeout/503 results do not prove
   that Gemini will be available or accurate for this electrical task. New image
   requests require a separately confirmed bounded batch.
4. Verify missed/false locations and types across drawing families, then reviewed
   quantities, pricing, save/reopen/reset, refusal and unresolved-item handling.
   Human entry alone is not proof of improved automatic recognition.

No old threshold tuning, small-switch OCR experiment, training, model call,
catalog edit or application/UI change was resumed during this audit.
