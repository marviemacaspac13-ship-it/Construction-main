# Plumbing tag and OpenCV corroboration plan

Status, 16 October 2026: research paused at the user's request. Do not execute
the next-stage or next-experiment suggestions below until research is explicitly
resumed. Current priority is the submission checklist in `../todo.md`.
The user's intended longer-term capability is detection of drawn fixture bodies
and symbols, not just printed tags. The experiment index and shape-first restart
plan are in [the checkpoint](DETECTION_RESEARCH_CHECKPOINT_2026-10-16.md).

## Objective

Improve plumbing fixture recognition while preserving the current safe estimate
contract: OCR-read fixture tags remain the only source of counted quantities
until a CV method demonstrates reliable, independently reviewed results.

## Current implementation

`_read_plumbing()` retains each accepted tag's label, image-space center and OCR
confidence in `PlanSchema.fixture_tag_observations`. The original tag counts
still drive pipe and fitting quantities. The observations are included in the
saved input snapshot and estimate audit record so a reviewer can locate each
count on the source sheet and a later CV evaluation can associate candidates
with tags.

This is an evidence-capture improvement, not an activated object detector.
Current template matching remains unsuitable for plumbing: the 11 October
evaluation produced 33 AWC candidates on a sheet with two known water closets,
and the strongest hits included tables, wall intersections and text. Other
fixture references either produced no matches or large false-positive counts.
Those crops remain research candidates, outside the active symbol library.

## Next stages

1. **Review the captured evidence.** On a family-diverse set of plumbing plans,
   compare every OCR observation with the drawing and annotate missed tags.
   Separate original layouts by content hash before evaluation; duplicate views
   of one plan are not independent examples.
2. **Evaluate tag-anchored OpenCV candidates offline.** Search only a measured
   neighborhood around each tag using fixture references. Record candidate
   distance, score, reference identity and reviewed outcome. Include untagged
   fixture searches as a separate diagnostic to measure missed tags, not as
   count additions.
3. **Set acceptance criteria before tuning.** Review every match and every
   unmatched tag on development plans, then freeze thresholds. On held-out,
   hash-distinct layouts, report precision, recall and per-class errors at a
   declared overlap criterion. Include negative contexts such as dimensions,
   walls, tables, labels, sinks and appliances.
4. **Promote only corroboration first.** If the held-out evidence supports it,
   expose CV agreement as review metadata while keeping tag counts authoritative.
   Do not increment, decrement or reclassify fixture counts from CV until a
   separate acceptance set demonstrates that this improves counts without
   creating unsafe estimates.
5. **Consider count fallback only after validation.** A future fallback needs
   complete-view labels, independently checked annotation coverage, documented
   source permissions, and a clear refusal rule for uncertain or unseen plan
   styles. Re-run the estimate and quantity-correction contract checks before
   changing production behavior.

## Submission scope

With the 18 October deadline, the useful deliverable is auditable tag evidence
and a frozen offline evaluation protocol. Do not train or activate a plumbing
template/model on the currently rejected references: the existing measurements
do not support a reliable automatic fallback.

## Stage 1 implementation — 15 October 2026

`scripts/review_plumbing_tags.py` now exports frozen OCR observations, source/code
hashes, drawing families, route decisions, overlays and a separate review record.
It keeps refused reads as offline evidence and asserts that capture preserves
production counts. Six selected views cover five recorded families; the two
cafeteria depictions remain one family despite different pixel hashes.

See `datasets/tag-evidence-stage1/REVIEW_FINDINGS.md` for the visual audit and
before/after diagnostic. Every returned observation was inspected by the same
agent; independent review and complete all-class missed-tag coverage remain open.
The public-restroom total concealed one duplicate WC observation and three
duplicate FD observations. `scripts/probe_tag_duplicates.py` evaluates canonical
tag deduplication offline using the existing OCR distance rule. It removes these
four duplicates but recovers no missed tags. Production is unchanged.

Next: independently review tag coverage and the deduplication proposal on more
densely labelled views; then measure tag-to-fixture neighborhoods for stage 2.
Do not treat these previously exposed views as untouched held-out acceptance data.

Second visual pass completed the clear supported-tag inventory on the six selected
views: see `datasets/tag-evidence-stage1/SECOND_REVIEW.md`. The restroom has
48 tags, 32 recovered locations and 16 misses; four extra observations are
duplicates. The fixed 25-pixel candidate is rejected because it merges distinct
urinal tags in a perfect-read coordinate test. Preserve OCR text extents before
evaluating a geometry-aware duplicate rule. Same-agent review does not satisfy
independent acceptance; one residential drain transcription remains uncertain.

OCR now retains optional original-image quadrilaterals, including inverse rotation
and tile translation, without changing counting. A frozen offline same-class
polygon-IoU >= 0.5 probe removes three of the four reviewed duplicate observations
and preserves the four manually bounded U tags in coordinate-scale checks.
The remaining FD pair has IoU 0.455; the threshold was not adjusted after seeing
this result. See `datasets/tag-geometry-stage1/FINDINGS.md`. No production
deduplication change or CV count fallback was promoted.

The missed-tag trace completed on 16 October: see
`datasets/tag-miss-diagnostic/FINDINGS.md`. Of the 16 restroom misses, ten have
wrong/empty local readings, four have correct readings below the OCR 0.5 cutoff,
one is a spaced `C. O.` rejected by parsing, and one U has no local detector
proposal. None is primarily lost to exact-string merging or legend suppression.
The diagnostic captures all 52 OCR calls and pre-confidence-filter readings while
reproducing the existing final observations exactly. Next priority is bounded
cleanout parsing and output-driven recognition rereads, not global threshold
lowering. These findings apply to the reviewed sheet, not all drawing families.

Cleanout spacing repair is implemented on 16 October. Complete spaced CO tokens
are accepted, with overlapping cleanout polygons deduplicated; other classes
retain their existing behavior. Six frozen OCR reads reproduce all prior route
decisions and non-cleanout counts. The restroom gains one real cleanout (3 -> 4),
with no priced-material change. See `datasets/cleanout-spacing-fix/FINDINGS.md`.
190 tests pass. The general deduplication and OCR reread experiments are not
promoted by this narrow fix.

The frozen output-driven two-crop recognition reread completed on 16 October:
`datasets/tag-reread-v1/FINDINGS.md`. Across six views and 524 selected regions,
it recovers no additional tag. The restroom remains 33 distinct correct locations,
four duplicate observations and 15 misses after the cleanout fix. Selection
reaches 14 of those misses; the remaining U lacks a proposal. Reject integration
of this reread policy. Next test recognizer capability on short labels and fresh
families rather than lowering the frozen confidence/agreement requirements.
