# Detection research checkpoint — 16 October 2026

> Update, 17 October: a subsequent user-requested training-free trial makes Gemini
> the current candidate for a limited reviewed API prototype. Two user-supplied
> responses cover 27 visually checked WC/LAV locations. Actual model identity and
> repeatability are unverified; production is unchanged. See the
> [new decision and evidence](GEMINI_FIXTURE_TRIAL_2026-10-17.md).
> The pause and restart instructions below describe the earlier checkpoint;
> broader training/OCR experiments remain paused.

Subsequent user instruction resumed only same-sheet template matching. The bounded
trial is recorded in [assisted template findings](datasets/assisted-template-trial-2026-10-16/FINDINGS.md).
All other research below remains paused. No production promotion occurred.

## Decision and user intent

Pause detection experiments. Preserve existing files, data, overlays, labels,
weights, protocols and negative results in place. Do not delete, retrain, install
new model dependencies, change thresholds or promote a candidate merely because
this file lists a future step. Resume only when the user explicitly requests it.
Active work is submission readiness in [todo.md](../todo.md).

The user wants to detect fixture bodies and graphical symbols: for example,
locate a toilet or lavatory without requiring WC/LAV text. Recent OCR work
improves label counting and cannot meet that requirement by itself. Earlier
shape-detector experiments already exist and must not be presented as a new
untried direction.

## Current implementation to preserve

- Floor plans: metric dimension OCR and deterministic derivation/assumptions.
- Electrical: reference-symbol template matching, ring filtering and minimum
  device guard. Adjacent-text symbol relabeling is disabled by default.
- Plumbing: tiled text OCR and supported tag counting. Complete spaced CO tokens
  are accepted; overlapping cleanout polygons count once. Cleanouts carry no
  material allowance and cannot satisfy the minimum-fixture floor.
- OCR retains optional text quadrilaterals internally and in offline exports.
  Saved PlanSchema observations still hold tag, center and confidence.
- General WC/FD polygon deduplication, recognition rereads and learned fixture
  detectors are not connected to production estimating.

Latest reviewed restroom: 48 clear supported printed tags; 33 distinct locations
recovered, 15 missed, four extra duplicate WC/FD observations. Total observations
are 37. These are tag metrics, not a 48-fixture inventory. The separate fixture
body inventory on that view contains 11 WC and 12 LAV. Do not mix denominators.

Latest narrow parser verification: 190 tests passed, nine OCR tests deselected;
six cached real-image OCR replays preserved refusals and priced materials. The
reread experiment had 35 focused tests pass. These are historical scoped checks,
not a fresh full-suite, HTTP, frontend or live-database acceptance result.

## Recent experiment register

| Work | Measured result | Decision and restart artifact |
| --- | --- | --- |
| Tag evidence capture and visual inventory | Six views, five families; exposed four duplicate observations and 16 original misses | Keep evidence tooling. [Review](datasets/tag-evidence-stage1/SECOND_REVIEW.md), inventory/review JSONs beside it |
| Canonical 25px deduplication | Removed four duplicates but merged distinct urinal tags in coordinate checks | Reject. `scripts/probe_tag_duplicates.py`; `datasets/tag-evidence-stage1/duplicate-probe.json` |
| Polygon-overlap deduplication | Removed three of four duplicates; no recall gain | Offline only. [Findings](datasets/tag-geometry-stage1/FINDINGS.md), frozen policy and predictions beside it |
| Missed-tag trace | Ten wrong/empty readings, four correct readings below 0.5, one spaced CO parser loss, one unproposed U | Diagnostic complete. [Findings](datasets/tag-miss-diagnostic/FINDINGS.md), raw trace and diagnosis beside it |
| Cleanout spacing | Cleanouts 3 -> 4; correct tag locations 32 -> 33; no price change | Implemented. [Findings](datasets/cleanout-spacing-fix/FINDINGS.md), `scripts/compare_cleanout_spacing.py` |
| Two-crop recognition reread | 524 selected regions on six views; no added supported tag; no final observation change | Reject integration. [Findings](datasets/tag-reread-v1/FINDINGS.md), policy/predictions/metrics and `scripts/probe_tag_reread.py` |

The missed-tag tracer explicitly preserves the pre-spacing-fix tokenizer to
explain the historical 16 misses. It does not describe current parser behavior
for CO. Other comparison tools may likewise assert frozen baselines; inspect
their declared scope before running them against changed production code.

## Earlier shape-detection research to retain

| Experiment family | Outcome/reference |
| --- | --- |
| Supplied plumbing legend templates | Large false-positive counts; not admitted to the active library. [Reference review](PLUMBING_REFERENCE_REVIEW.md), `reference_candidates/2026-10-11/` |
| Four-sheet WC/LAV annotation and detector pilot | 33 fixture bodies across three families; exploratory, not broad acceptance. [Pilot](datasets/plumbing-pilot/README.md), [results](datasets/plumbing-pilot/PILOT_RESULTS.md) |
| Assisted and automatic exemplar matching | Preserve the distinct assisted-input and automatic-input evaluations. [Assisted results](datasets/plumbing-pilot/exemplar-match/RESULTS.md), [automatic results](datasets/plumbing-pilot/automatic-exemplar/RESULTS.md) |
| Expanded YOLO11n WC/LAV detector | 11 correct / 18 false / 16 missed on 27 evaluated bodies at IoU 0.5. Rejected. [Results](datasets/plumbing-expanded/RESULTS_2026-10-14.md) |
| FloorPlanCAD transfer | Transfer reduced some false hits but remained insufficient. Label coverage/subtype errors required subsequent correction. [Transfer results](datasets/floorplancad-audit/TRANSFER_RESULTS_2026-10-15.md); preserve later coverage records in the same directory |
| New raster drawing families | Fresh 19-body comparison: 10/6/9 -> 12/16/7 correct/false/missed; extra recall cost many false hits. Rejected. [Results](datasets/raster-fixtures/RESULTS_2026-10-15.md) |
| Joint WC/LAV/other classifier | Fresh eight-body comparison: 6/6/2 -> 6/5/2; typing regressions on exposed retail. Rejected. [Results](datasets/joint-fixtures/RESULTS_2026-10-15.md) |
| WC proposal-recall fine-tune | Fresh three-WC comparison: 0/2/3 -> 0/1/3 at IoU 0.5. No recovery gain. Rejected. [Results](datasets/wc-proposal-recall/RESULTS_2026-10-15.md) |

These rows describe different datasets and protocols; do not pool their totals
or rank them as if they shared an untouched test set. The full chronology,
checkpoint identities and isolated training paths are in
[the earlier handoff](../HANDOFF_2026-10-15.md). Historical runs are retained,
not rerun or newly verified by this documentation update.

## Shape-first restart plan — paused

Desired eventual flow:

`plan image -> overlapping tiles -> fixture/symbol bounding boxes -> duplicate/conflict review -> confirmed object counts -> existing estimating rules`

OCR can supply an adjacent variant label or schedule reference, but shape
proposals should not require a readable tag. A drawn object must count once
even when both its shape and label are found. Plumbing WC/LAV bodies have no
direct catalog SKU; map confirmed canonical counts through the existing rules.
Electrical symbol families can retain reference matching where already validated.

1. **Define one bounded target.** Start with WC and LAV bodies in supported plan
   conventions. Do not promise all fixture classes or infer outlet gangs from
   a shape that does not encode them. Keep kitchen/utility basins, urinals and
   ambiguous objects explicit rather than silently treating all sinks as LAV.
2. **Audit and extend existing labels before another training run.** Reuse the
   existing annotation formats and tooling. Confirm complete views; add missing
   drawing styles and confusing non-targets such as text, tables, walls, kitchen
   fixtures and appliances. The client has no additional data; use existing
   lawful local sources and independently reviewed additions, not an assumed
   future client upload. Preserve uncertainty and source attribution.
3. **Reserve genuinely new families before model selection.** Exact image hashes
   alone do not separate buildings. Keep crops, rotations, alternate renders and
   related floors together. Previously tested families are development examples.
4. **Reuse the isolated shape-detector pipeline.** The existing YOLO11n workflow
   already uses overlapping 640-pixel tiles with 480-pixel stride. Review its
   code and failures rather than introducing another framework by default.
   Tiling helps preserve small-object detail; it does not fix incorrect labels
   or missing drawing-family coverage. Do not install training dependencies into
   the application environment merely to reopen research.
5. **Predeclare one bounded comparison and stop rule.** State classes, baseline,
   training budget, checkpoint rule, thresholds, IoU metric and acceptable error
   rates before inference. Review every predicted/missed location; report each
   class and family, runtime and count error. If it fails, retain the result and
   stop rather than making sequential test-set-driven adjustments.
6. **Integrate reviewed proposals before automatic estimating.** Initially show
   detected objects as proposed boxes with accept/reject/correct controls in a
   separately scoped future UI change. This is not implemented today. Keep low-
   confidence or conflicting detections from silently determining quantities.
   Automatic count authority requires a separate successful acceptance set and
   estimate/correction contract checks.

General-purpose pretrained models do not arrive with reliable construction-symbol
classes. Custom object detection requires labeled examples; YOLO's output is
bounding boxes, class labels and confidence. [Official detection documentation](https://docs.ultralytics.com/tasks/detect).
Overlapping sliced inference is an established method for small objects in large
images, but installing SAHI is not necessary when the existing tiling code already
serves that purpose. [Official SAHI guide](https://obss.github.io/sahi/quick-start/).

For a short-deadline demonstration, a user-marked exemplar can support assisted
same-sheet matching, but that is a different input contract and is not universal
automatic fixture recognition. Previous exemplar experiments must be reviewed
before even that work is resumed. No new demo mode is authorized by this plan.

## Preservation and restart checklist

- Keep the current working tree and existing `.venv-training` research setup;
  inspect status before staging or cleanup. There are extensive prior changes.
- Preserve manifests, family splits, frozen policy JSON, original/independent
  annotations, prediction files, overlays and local checkpoint hashes.
- Source-derived images, datasets and weights may be ignored/local-only. A Git
  commit alone is not a complete backup. This update neither deletes them nor
  claims to have created an external backup.
- On resumption, first read this checkpoint, `todo.md`, the earlier handoff and
  the chosen experiment's own protocol. State one hypothesis and its evidence
  gap. Do not resume every item in the historical backlog.
- First finish the submission regression and correction-workflow verification;
  those checklist items remain pending until actually executed.
