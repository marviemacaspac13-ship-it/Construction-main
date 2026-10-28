# `train-00` dataset feasibility pilot

**Superseded finding, 14 October 2026:** the paired SVGs contain `semantic-id` and `instance-id` annotations on individual primitives, not only CAD layers. The [metadata recovery audit](../backend/datasets/floorplancad-audit/README.md) recovers 1,203 toilet and 2,110 unspecified sink instances across 937 tiles using the authors' raw class remapping. Therefore the statements below that every label must be recreated manually are no longer correct. Source extent conventions, sink subtypes, drawing-family grouping and the authors' noncommercial annotation licence remain unresolved for production training. The original feasibility record is retained below as history.

Reviewed 13 October 2026. This is a read-only feasibility review; no training run or production detector change was made.

## Inventory

- 3,760 PNG plan tiles, each paired by filename with an SVG.
- 3,760 rendered files in `coco_vis/`.
- The inspected PNG/SVG pair represents the same plan area: the SVG uses a 0–100 viewBox and the PNG is a 1000 × 1000 raster.
- The SVG stores vector drawing elements inside CAD layers. A review of 200 SVGs found 78 distinct layer labels. Common examples included `WALL`, `WINDOW`, `STAIR`, `COLUMN`, `S-洁具` (sanitary fixtures), and `VPIPE-消防` (fire pipe). Labels are source CAD organization, not TRACE item IDs.

## What the sample shows

The `coco_vis/0005-0002.png` visualization has colored regions and red labels for examples such as single/double doors, blind window, sink, elevator, and air conditioner. This is useful evidence that object-level annotations were used to produce visualizations. However, the `train-00` folder contains no COCO JSON, YOLO text labels, or class-name file. The rendered overlay alone is not a reliable machine-readable annotation source.

The matching SVG contains vector geometry and layer membership, but its layers are broad and inconsistent with TRACE's 28 detector classes in `backend/data.yaml`. For instance, `S-洁具` groups sanitary items rather than distinguishing toilet, lavatory, or floor drain; pipe layers denote broad systems rather than the catalog's specific pipe and fitting labels. The inspected sample is an architectural plan tile, not a labeled electrical plan.

## Fixture and object detection check

The raw raster tiles do contain recognizable drawn objects. In `0486-0013`, the preview marks a toilet and sinks; inspection of the raw PNG confirms the toilet outline and both basin shapes are visible as geometry, not just as text. The preview also marks appliances and furniture, which are outside TRACE's current takeoff targets. A three-box manual example for the toilet and sinks is in [`manual-pilot/fixture_boxes.csv`](manual-pilot/fixture_boxes.csv), with a visual check at [`manual-pilot/0486-0013-fixture-review.png`](manual-pilot/0486-0013-fixture-review.png).

This is evidence the dataset can support object detection for at least some plumbing fixtures. It does not establish that all 3,760 tiles contain fixtures or that all target classes have enough examples. Electrical outlets and switches are not confirmed: a few SVG layers contain the word `插座` (outlet), but the corresponding preview/raw sample did not provide an unambiguous, labeled outlet example. No switch instance was verified in this review.

## Fit for TRACE

| TRACE target | Evidence in this pilot | Assessment |
| --- | --- | --- |
| Electrical symbols (outlets, ceiling receptacles, switches) | No corresponding labeled classes established from the reviewed layers/overlay | Not ready; the current symbol detector cannot be trained from layer names alone |
| Plumbing fixtures | Broad sanitary CAD layer and a visible sink annotation; no confirmed per-fixture label file | Possible source for a separate annotation effort, but not verified fixture ground truth |
| Pipes and fittings | Broad CAD pipe-system layers occur in the sample | Potential geometry source; layer-to-catalog class mapping and instance boundaries remain unverified |
| Doors/windows | Explicit labels appear in the visualization | Adjacent to TRACE's openings problem, but not a direct match for current priced takeoff classes |
| Floor-plan dimensions and quantities | Dimensions are drawn as vectors and text | Not equivalent to the OCR extraction's validated dimension chains or quantity labels |

## Decision

`train-00` is **not plug-and-play training data for TRACE**, but it can help with object recognition: this review verified visible toilet and sink shapes and recorded three exploratory boxes. Its usefulness is currently strongest for plumbing fixtures and other architectural objects that are visibly drawn. Suitability for TRACE's electrical outlet/switch detection remains unproven. The missing annotation source means each training label would need to be created and checked independently. Before scaling up, identify which exact fixture classes clients need, label all their instances in a small set of tiles, review those labels, and split by original plan/building rather than by tile.

The owner confirmed that the original annotation file is unavailable. A tiny manual labeling exercise is recorded in [`manual-pilot/`](manual-pilot): four approximate door boxes on two tiles and three fixture boxes on one tile. This tests whether objects can be labeled directly from the raster; it does not establish readiness for model training. The labels are exploratory, not independently reviewed, and must not be used as training or evaluation data.

Do not import the visible overlays or infer detector labels directly from layer names as ground truth. The pilot does not establish that the source drawings are independent buildings, that all visualization labels are correct, or that any trained model would improve TRACE's current readers.
