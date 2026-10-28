# Reviewed electrical devices and boxes

Later on 26 October, new reviewed image estimates were extended with the original
light/convenience-outlet wire and conduit allowances. The historical
`devices_and_boxes` scope below remains supported for saved-version replay.
See [restored allowance scope](ELECTRICAL_ALLOWANCES_RESTORED_2026-10-26.md)
for the current upload behavior and its validation.

Implemented 26 October 2026 following the user's choice of an explicitly partial
estimate. This completes the workflow implementation checkpoint, not R25 general
recognition acceptance or a full electrical installation estimate.

## User flow

1. Choose Electrical Plan and upload a PNG/JPEG/WebP. Following the subsequent
   user instruction, there is no detector or estimating-mode selector. The image
   enters the reviewed partial workflow automatically. Existing saved estimates
   and the legacy direct estimating API retain their original rules.
2. `POST /api/electrical/proposals` attempts configured free-tier-eligible Gemini
   models first when enabled. If unavailable, busy, timed out or unusable, it runs
   the installed local template matcher automatically. It returns one inventory,
   never Gemini counts plus local counts, with an owner/image-bound signed receipt.
   The same partial review follows either reader. Zero/sparse local proposals may
   be reviewed, but do not themselves produce an automatic estimate. See
   [Gemini integration and live trial](ELECTRICAL_GEMINI_SETUP_2026-10-26.md).
3. Review the whole drawing. Select, move or resize boxes; add missed devices;
   correct their class, product, gang count and switching function. Rejecting a
   proposal retains an explicit exclusion and reason. Original proposals remain
   separate from corrected choices. Restore proposals clears review confirmation.
4. Every included device needs an explicit catalog selection. Every included box
   needs a selected UTB01/JCB01 and explicit compatibility confirmation; otherwise
   the reviewer must state why that box is outside scope. No universal box fit is
   inferred from gang count. Changing product invalidates box confirmation.
5. Confirm the reviewed inventory and partial scope. Image estimation verifies
   the receipt's owner, exact bytes/dimensions, signature and four-hour expiry.
   It uses the reviewed counts directly; it never adds automatic counts again.
6. Results and CSV identify **partial estimated cost** and exclusions. Saved
   originals reopen with included/excluded review boxes. Project price edits
   replay the same scope and counts; use Replace / rescan to revise assemblies.

## Pricing boundary

The stored `electrical_review.estimate_scope = devices_and_boxes` selects a
separate BOM path, with `electrical_review_v1.device` and
`electrical_review_v1.compatible_box` provenance. It does not invoke the existing
electrical wiring rules. Legacy snapshots omit the new estimate output keys.

| Device | Partial eligibility |
| --- | --- |
| Ceiling outlet | Explicit CLR01/02/03 selection; no inferred receptacle size |
| Convenience outlet | Explicit OT01/02/03 selection; any supplied gang count must agree; socket strokes do not establish gang count |
| One-way switch | Explicit SW01/02/03, confirmed one-way function and matching 1/2/3 gang count; one physical assembly purchases one set |
| AC outlet | Explicit generic ACO01 device only; no equipment rating, conductor or protection inference |
| GS, three-way, four-way or unknown | Unresolved; no nearest-product substitution. Resolve or explicitly exclude with a reason |

Wire, conduit, breakers, panels, switch legs and circuit design are excluded.
Any unresolved included device, duplicate assembly, excessive box overlap,
unconfirmed box or all-excluded/empty inventory blocks estimation. Partial plans
cannot carry runs or other trade geometry, or aggregate counts differing from
their reviewed assemblies. Numeric edits therefore cannot detach box quantities
from the physical assemblies. No catalog prices or engineering defaults changed.

The receipt secret defaults to an ephemeral process secret. Set
`ELECTRICAL_REVIEW_SECRET` to a stable, private shared secret when using multiple
workers. Restarting without it invalidates outstanding unsaved reviews; already
saved review evidence still reopens. No secret was configured by this work.

## Validation and limitations

- 705 non-OCR backend checks passed, including 14 new partial-scope cases and
  authenticated-route coverage. The tests exercise function/gang distinction,
  no wiring-rule execution, explicit product/box selection, exclusions, price
  replay/reset, foreign/tampered inputs and recomputed save eligibility.
- 40 frontend helper/storage checks passed. TypeScript and production build
  passed; the existing bundle-size advisory remains. The interface detector
  reported no findings. OCR readers and detector thresholds were unchanged.
- Browser acceptance used the existing signed-in account and a new, clearly
  named `ACCEPTANCE ELECTRICAL PARTIAL 2026-10-26` project. Source: checked lighting
  sheet `tests/fixtures/plans/Data Set/Electricalplan/IMAGE/11.png`.
- The matcher proposed nine ceiling outlets. Product selection and nine explicit
  box omissions were reviewed. Two **synthetic** switch records exercised manual
  addition, one-way/two-gang selection, compatible-box confirmation, keyboard
  move/resize and explicit three-way exclusion. These are workflow fixtures,
  not additional ground truth or a verified switch takeoff of that drawing.
- Saved output: CLR01 9 × P22, SW02 1 × P169, UTB01 1 × P15 = **P382**.
  Full reload retained scope, exclusions, original image and all eleven review
  boxes; exported CSV retained partial scope and all exclusion reasons.
- A project-only SW02 price override from P169 to P100 saved/reloaded at **P313**.
  Resetting to the original prices saved/reopened at **P382**, with the original
  review boxes and scope retained. One new acceptance project was created; no
  existing user project was edited or deleted.

At the original partial-workflow checkpoint, automatic switch recognition was
unsupported and no provider requests were made. The subsequent user-approved
Gemini integration now proposes additional device classes when available; local
fallback still cannot automatically count switches. The bounded live trial did
not yield usable detections, so electrical recognition improvement and the
generalization/location benchmark remain unverified. Full client revision
acceptance cannot be inferred from either implementation checkpoint.
