# TRACE — Plan Processing & Cost Estimation System Requirements

Consolidated list of everything needed to build the full pipeline: file
upload through to a client-facing cost estimate with an AI-generated
explanation. Covers both CAD file input (DWG/DXF) and image input
(photos/scans of plans).

---

## 1. Core strategy

- Split the problem into two input paths (CAD vs image) that both produce
  the **same structured plan schema** as output. Everything downstream of
  that point — rule engine, pricing, explanation — runs identically
  regardless of which path the file came through.
- Keep all quantity and cost math in a **deterministic rule engine**, never
  in a machine learning model. ML/AI is only used to *extract* data from
  the source file or to *narrate* numbers that have already been computed.
- Every stage that involves uncertainty (OCR reads, symbol detection,
  layer-name mapping) needs a confidence check and a human review path —
  never auto-accept low-confidence extractions silently.

---

## 2. CAD file path (DWG / DXF)

**What's needed:**
- File validation on upload: extension check, file header/magic-byte
  check, DWG version check, corrupt-file check — before queuing further
  processing.
- DWG-to-DXF conversion, since DWG is a closed format and can't be parsed
  directly. Choose one:
  - Autodesk Platform Services (APS) — cloud-hosted, no infrastructure to
    manage, has usage costs.
  - ODA File Converter — free, self-hosted, run as a CLI step inside a
    worker.
- DXF parsing library (ezdxf) to read entities, layers, blocks, and text
  once the file is in DXF form.
- A maintained **layer/block-name mapping table**, since different firms
  name layers and blocks inconsistently. This table is what tells the
  extraction engine which entities represent walls, pipe runs, fittings,
  fixtures, electrical symbols, etc.
- A **symbol/block dictionary** mapping CAD block references (fittings,
  fixtures, electrical symbols, door/window codes) to your internal
  material/category taxonomy.
- Unit and scale detection from the DXF header, with verification rather
  than blind trust — some files have incorrect or default unit settings.
- Geometry calculations for length (pipe runs, wall runs) and area (room
  polygons) from the parsed coordinates.

---

## 3. Image file path (photos / scans of plans)

**What's needed:**
- Preprocessing: deskew, denoise, contrast correction, and cropping to
  isolate regions of interest before running OCR or detection — this
  meaningfully improves downstream accuracy. (OpenCV)
- Text and dimension extraction:
  - For plans with printed room dimensions (e.g. "360 X 379"), OCR or a
    vision-language model doing structured extraction should be the
    **primary** method — not pixel measurement.
  - PaddleOCR is a better fit than Tesseract for plans with rotated,
    stylized, or cluttered text.
  - A VLM call ("return each room, its dimensions, and door/window codes
    as JSON") can outperform classic OCR by using visual context to
    correctly associate labels with the right room, especially on
    photorealistic/rendered plan images.
- Scale calibration for plans without printed dimensions: attempt
  auto-detection (scale bar, known reference like standard door width),
  but always require user confirmation before any quantity is computed
  from pixel measurements. This is the single highest-leverage accuracy
  fix on the image path.
- Symbol/fixture detection model (YOLOv8, custom-trained) for plans without
  printed dimensions, or as a secondary validation check on plans that do
  have them. Requires a labeled training dataset specific to your plan
  types — pretrained/general-purpose weights will not recognize floor
  plan symbols out of the box.
- Wall/room segmentation model as a fallback for undimensioned,
  hand-drawn, or low-detail plans — lower priority to build; can be
  deferred until the OCR/VLM + CAD paths are working well.
- A **synonym/room-type dictionary** to normalize inconsistent labeling
  ("W/KITCHEN," "W.C.," "SIT OUT") into your internal room-type taxonomy.
- A **cross-check step**: when a declared total area/cost is printed on
  the plan, sum the extracted room areas and compare against it. A
  mismatch is a strong, cheap signal that something was misread.

---

## 4. Shared structured plan schema

- One consistent output format that both the CAD path and the image path
  populate: rooms (with area), walls (with length/type), fixtures,
  fittings, symbols/codes, and confirmed scale/units.
- This schema is the single hand-off point between "extraction" and
  "computation" — nothing downstream should need to know whether the
  source was a DWG file or a photo.
- Stored as its own record (not just held in memory), so it can be
  queried later for audits, re-processing, or training data.

---

## 5. Rule engine and cost calculation

- A maintained, versioned set of takeoff formulas (coverage rates, waste
  factors, standard material requirements per unit area/length). This
  logic stays explicit and auditable — never learned by a model.
- A defined Bill of Materials (BOM) output format: material name, type,
  quantity, unit — generated by applying the rule engine to the
  structured plan schema.
- A join between BOM items and your materials price table, with an
  explicit policy for unmatched items (flag for review, never silently
  zero out or skip).
- Cost calculation: quantity × unit price per BOM row, summed to a total.
  Log which price-table version/timestamp was used per estimate so
  historical estimates don't silently shift if prices update later.
- A sanity-check step before treating the total as final — e.g. comparing
  against a declared area/cost benchmark if the source plan provided one.

---

## 6. AI explanation layer

- Default: a **template-based explanation engine** that fills pre-written
  sentence structures with values from the already-computed estimate
  (total cost, dominant material, cost breakdown, item counts). This
  cannot hallucinate a number, since it only ever inserts values already
  present in the estimate data — no free-text generation involved.
- Optional fallback: for open-ended questions the templates don't cover,
  call an LLM — but only with the structured estimate JSON as input
  (never the raw plan), with a system prompt that explicitly forbids
  introducing any number not present in that JSON.
- A verification step on any LLM-generated text: extract every number in
  the output and confirm each one appears in the source JSON before
  showing it to the user; discard/regenerate if not.
- Scope discipline: the explanation layer only narrates numbers the rule
  engine already computed. It should never be asked to compute a new
  number itself (e.g. "what if I used a cheaper material" requires
  re-running the rule engine with modified inputs, not asking the
  explanation layer to reason about a cost delta).

---

## 7. Symbol detection model retraining pipeline

- A correction-capture flow in the app: when a user flags a wrong symbol
  detection, store the image crop and the correct label.
- Corrections accumulate into a versioned training dataset rather than
  being used one-off.
- A minimum-new-samples gate before retraining is triggered (e.g. 100+ new
  corrected labels) — retraining on too few new samples risks overfitting
  to noise and wastes compute.
- Training runs use **early stopping** (a patience parameter) rather than
  a fixed large epoch count, so the model stops improving based on
  validation performance, not an arbitrary number.
- Confidence threshold and IoU threshold are tracked as separate settings
  from each other and from any business-level "acceptable error" target —
  they measure different things and shouldn't be collapsed into one
  number.
- Training must run as a background job on a worker (not synchronously in
  a request) — this is a minutes-to-hours process.
- **Gated promotion**: a newly retrained model only replaces the
  production model if it scores better on a held-out validation set.
  Never auto-replace based on trust alone, and always keep the previous
  version available for rollback.
- If exposing a manual "retrain" trigger to an admin view, keep it simple
  (a "train now" action with sane defaults) rather than exposing raw
  hyperparameters to non-specialist users.

---

## 8. File processing infrastructure

- File upload goes directly to blob storage (Supabase Storage), never
  processed synchronously inside the upload request.
- A job record (in Supabase's Postgres database — no separate database
  needed, Supabase's database is Postgres) tracks each file through a
  fixed status sequence: uploaded → converting/scanning → extracting →
  computing → done (or failed at any point). This record is what the
  frontend polls or subscribes to for live progress.
- A worker service (Python) that either receives a direct trigger or
  polls for new jobs, downloads the file from storage to local disk,
  processes it, and deletes the local copy immediately afterward — the
  worker's local filesystem is disposable scratch space only.
- A queue system so processing doesn't block on volume, and so failed
  jobs can be retried without requiring the user to re-upload.
- Structured plan data and the resulting estimate are saved as their own
  records linked to the job, not just bundled as a blob on the job row —
  needed for later querying, audits, and training data.
- Real-time or polling-based status updates to the frontend so the
  existing Analysis Status UI reflects true pipeline progress.

---

## 9. Human-in-the-loop / review requirements

- Confidence scoring at every extraction stage (OCR reads, symbol
  detection, layer-name mapping) — not just a single overall confidence
  number for the whole plan.
- Anything below the confidence threshold is routed to manual review
  before being treated as final, rather than auto-accepted.
- Any BOM item with no matching entry in the symbol/block dictionary or
  the materials price table is flagged explicitly, never silently dropped
  or defaulted.
- A per-firm/per-user layer-naming and symbol-mapping profile that
  improves automatically as corrections are made on repeat projects from
  the same source.

---

## 10. Suggested build order

1. CAD path (DXF parsing + rule engine + BOM + cost calculation) — most
   deterministic, highest accuracy-per-effort, no ML dependency to stand
   up first.
2. Image path for dimensioned plans (OCR/VLM extraction + cross-check
   against declared totals) — second-highest accuracy-per-effort.
3. Template-based explanation engine — low risk, immediate client value,
   no infrastructure dependency.
4. File processing infrastructure (storage, job tracking, worker, queue)
   — needed to support both paths at real usage volume.
5. Symbol detection model (YOLOv8) and the undimensioned-image path — most
   effort, most dependent on having real user-uploaded plans as training
   data, so reasonable to defer until the above is validated.
6. Correction-capture and retraining pipeline — only becomes useful once
   the symbol detector is live and generating real corrections to learn
   from.
