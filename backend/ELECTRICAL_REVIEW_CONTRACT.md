# Electrical review backend contract

Current implementation update: the approved **devices-and-boxes partial workflow**
is now implemented in [ELECTRICAL_PARTIAL_WORKFLOW_2026-10-26.md](ELECTRICAL_PARTIAL_WORKFLOW_2026-10-26.md).
It adds authenticated local proposal and confirmation routes, a review interface,
and separate partial pricing. The original `standard` review boundary documented
below still blocks switch/AC allowances. Its numeric-correction behavior does not
apply to the new partial scope, whose counts remain tied to reviewed assemblies.
The following sections retain the earlier backend checkpoint as historical context.

Implemented 26 October 2026 as the separately approved backend/offline checkpoint.
This is a review-data boundary, not an electrical recognizer or a visible review
screen. No model requests, frontend controls, new HTTP routes or new switch/AC
pricing rules were introduced. Existing automatic image paths remain unchanged.

## Stored evidence and decisions

`app/electrical_models.py` defines strict bounded records, separate from WC/LAV
plumbing evidence. An electrical observation stores:

- Stable observation and physical-assembly IDs, plus a positive-area bounding box
  in normalized `[ymin, xmin, ymax, xmax]` coordinates from zero to 1000.
- Device class: light point, convenience outlet, switch, AC outlet or unknown.
- Raw printed mark, adjacent text, nullable socket configuration, gang count and
  switching function, and uncertainty. These are separate attributes.

Provider observations cannot contain catalog SKUs, prices or aggregate counts.
`ElectricalChoice` separately records the user's product selection and include/
exclude disposition. Exclusion requires a reason. Every original proposal must
retain a decision, including rejected duplicates; an added observation can have
a new ID. Included assembly IDs must be unique, and included boxes whose IoU is
greater than 0.5 cannot be confirmed. This is a review conflict guard, not a
detector confidence or accuracy threshold. At most 500 proposals/choices are kept.

`ElectricalReview` retains the original proposals and accepted decisions, exact
image identity/dimensions, owner, provider/model provenance and confirmation time.
Eligibility is recomputed from choices; clients do not submit authoritative
assessment states or derived counts.

## Current pricing eligibility

| Reviewed observation | Current result |
| --- | --- |
| Light point, no conflicting attributes/product | CLR01, explicitly recorded as existing library default rather than a read size |
| Light point with explicit compatible product | CLR01/02/03, user product selection |
| Duplex convenience outlet with unknown/one gang and no product selection | Existing owner-selected OT01 default; gang was not inferred as read |
| Convenience outlet with explicit compatible product | OT01/02/03; a stated gang count must agree |
| Single/triplex/unspecified outlet without a selected product | Unresolved; socket count does not imply a gang/SKU |
| Switch, AC outlet, unknown class, incompatible product or conflicting attributes | Unresolved, even when GS/SW/ACO is selected |
| Explicit exclusion with a reason | Retained evidence, no priced device contribution |

A record containing an unresolved included device cannot become a priced
`PlanSchema`. Resolve it or explicitly exclude it first. An empty/all-excluded
review is refused rather than generating a zero-material estimate. Exclusion is
an explicit estimate-scope decision, not a claim that the device does not exist.
It must remain visible in the future review UI and is preserved in the ledger.

`reviewed_plan(review)` constructs absolute counts from the reviewed assemblies;
it does not accept or union another detector count. Existing outlet/lighting
calculation rules remain in force. Switch/AC allowances and GS/SW meanings are
still the unresolved work identified by the [audit](ELECTRICAL_REVIEW_AUDIT_2026-10-26.md).

## Confirmation boundary

`app/electrical_review.py` exposes local functions only:

1. `issue_review(raw, checked_owner, observations, provider=..., model=...)`
   validates the original image and produces a purpose-separated HMAC receipt.
2. `confirm_review(submission, raw, checked_owner)` requires `confirmed=true`,
   checks signature, owner, exact source hash/dimensions and a four-hour lifetime,
   and returns the confirmed evidence. Future-dated receipts are refused.
3. `reviewed_plan(review)` refuses unresolved/all-excluded reviews and derives
   the supported source fixture counts.

A future authenticated HTTP integration must call these functions with the
owner from its session dependency, never a request-body owner. This checkpoint
does not expose proposal/signing/confirmation endpoints or claim an end-to-end
electrical authorization flow. The stored evidence record by itself is not a
cryptographic proof that a future caller used `confirm_review`.

Optional `ELECTRICAL_REVIEW_SECRET` is server-only and separate from provider keys.
Without it a per-process random key supports local tests but pending receipts
do not survive restarts or transfer between workers. Use one stable shared secret
when the future multi-worker integration is enabled. No secret was configured
or changed by this checkpoint. Raw receipts are not copied into audit evidence.
Only upright static PNG/JPEG/WebP originals within existing byte/pixel limits
are eligible. No preprocessing, rotation or provider upload occurs here.

## Snapshot, correction and audit compatibility

`PlanSchema.electrical_review` is optional. When absent it is omitted from output,
preserving legacy save-request shapes and exact retry comparisons. When present
it belongs only to electrical plans, cannot coexist with WC/LAV evidence, and
cannot activate GS/SW/ACO or unrelated purchase products. Python callers that
bypass initial Pydantic construction are revalidated before reviewed estimation.

Original revision saves check source-hash and reviewed-assembly/count consistency,
and the save handler checks the review owner against its authenticated owner.
Supported later numeric corrections remain absolute overrides. They do not
rewrite original boxes or original proposal/choice evidence; reset starts from
the immutable original as before. Reviewed estimates receive electrical-specific
audit assumptions rather than symbol-only or WC/LAV wording. `audit.py` retains
the complete electrical evidence and derived mapping assessments.

The existing version-1 JSON snapshot and revision RPC store nested electrical
evidence without SQL schema changes. An isolated PostgreSQL test exercised
save/reopen/exact retry with included outlets and an explicitly excluded S3w
observation. No migration was applied to any live database. Draft unresolved
reviews can be serialized as standalone records, but this checkpoint does not
provide durable draft storage or save them as completed estimates.

## Verification

- 29 new focused Python cases cover geometry/type limits, unsupported classes,
  explicit product compatibility/exclusions, duplicate assemblies/overlaps,
  add/move/relabel, owner/image/signature/expiry confirmation, source snapshot
  replay, numeric corrections/reset, audit retention and mocked revision saves.
- Complete non-OCR backend run: **690 passed, 53 OCR tests deselected**, four
  existing dependency deprecation warnings; 12.78 seconds.
- Isolated revision/frontend-helper file: **18 checks passed**, including the
  additive evidence round trip with existing migrations.
- Frontend TypeScript checking passed. No frontend implementation changed;
  a new production build, browser acceptance and live database/model calls were
  outside this checkpoint. Full OCR tests were not rerun because readers did not change.

R25 remains incomplete. The next separately confirmed checkpoint is the supported
switch/AC product and material-rule decisions, followed by review UI/proposer
integration and actual drawing-level acceptance under the free-tier-only constraint.
