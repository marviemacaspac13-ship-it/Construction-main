from dotenv import load_dotenv
load_dotenv()

import traceback

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.vision.preprocess import preprocess_image
from app.vision.template_match import match_templates
from app.pricing import price_takeoff
from app.schemas import ScanResponse
from app.materials import load_catalog
from app import audit, templates_store
from app.extract.tags import count_tags, read_tiled, tally
from app.takeoff.constants import FIXTURE_PLUMBING, FIXTURE_TAG_PATTERNS
from app.takeoff.schema import PlanSchema

from pydantic import BaseModel

from app.extract.reader import read_plan_bytes
from app.extract.report import ImageEstimateResponse, report_from_extraction
from app.extract.to_plan import to_plan_schema
from app.takeoff.from_detections import plan_from_detections
from app.takeoff.estimator import EstimateResponse, estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import PlanSchema

VALID_PLAN_TYPES = ("Floor Plan", "Electrical Plan", "Plumbing Plan")

# Floor plans carry printed room dimensions, so they are read. Electrical
# and plumbing plans do not - their quantities are discrete symbols, so
# they are detected against uploaded references. Both paths end in the same
# PlanSchema and the same rule engine.
OCR_PLAN_TYPES = ("Floor Plan",)
# Read by counting printed tags rather than by matching symbols.
TAG_PLAN_TYPES = ("Plumbing Plan",)

# The fewest symbols a real electrical sheet can plausibly carry. The one
# plan with a hand count has 35; the sheets that match nothing real return
# two to five stray hits at the current threshold, and an estimate built on
# three detections is a near-miss dressed up as a reading. This is the same
# rule as the empty-result guard below, one step along: a result too sparse
# to be a drawing is not a cheaper building, it is a failed read.
MIN_DEVICES = 10


class EstimateRequest(BaseModel):
    plan: PlanSchema
    params: EstimatingParams | None = None

app = FastAPI(title="TRACE Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "http://localhost:5173"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/scan", response_model=ScanResponse)
async def scan_plan(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file (PNG/JPG).")

    # No reference images means nothing can possibly match. Returning an empty
    # zero-peso estimate here looks like a successful scan of a plan with no
    # materials on it, which is worse than saying so. An empty result AFTER
    # templates exist is a real outcome and still returns 200.
    if not templates_store.list_templates():
        raise HTTPException(
            422,
            "No symbol references have been uploaded, so nothing can be matched. "
            "Add a reference image for each catalog item in the Symbol Library, "
            "then scan again.",
        )

    raw_bytes = await file.read()
    image = preprocess_image(raw_bytes)
    detections = match_templates(image)
    return price_takeoff(detections)

@app.get("/api/materials")
def list_materials():
    return list(load_catalog().values())

@app.post("/api/templates")
async def upload_template(item_id: str = Form(...), file: UploadFile = File(...)):
    catalog = load_catalog()
    if item_id not in catalog:
        raise HTTPException(400, f"'{item_id}' is not a known catalog item_id.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file (PNG/JPG).")

    raw_bytes = await file.read()
    filename = templates_store.save_template(item_id, raw_bytes, file.filename or "template.png")
    return {"item_id": item_id, "filename": filename}


@app.get("/api/templates")
def get_templates():
    return templates_store.list_templates()

@app.delete("/api/templates/{item_id}/{filename}")
def remove_template(item_id: str, filename: str):
    deleted = templates_store.delete_template(item_id, filename)
    if not deleted:
        raise HTTPException(404, "Template not found.")
    return {"deleted": True}

@app.post("/api/estimate", response_model=EstimateResponse)
def estimate(request: EstimateRequest):
    """Price an already-structured plan description.

    Independent of how the plan was described - a form, OCR, detection, or
    a CAD parser all produce the same PlanSchema.
    """
    return estimate_plan(request.plan, load_catalog(), request.params)


@app.post("/api/estimate/image", response_model=ImageEstimateResponse)
async def estimate_image(
    file: UploadFile = File(...),
    plan_type: str = Form("Floor Plan"),
):
    """Read a dimensioned plan image and price it, with no human input.

    Returns the estimate alongside what the reader saw and how much of it
    checks out, so a low-confidence result is visible rather than implied.
    """
    if plan_type not in VALID_PLAN_TYPES:
        raise HTTPException(
            422,
            f"Unknown plan type '{plan_type}'. Expected one of: "
            f"{', '.join(VALID_PLAN_TYPES)}.",
        )

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file (PNG/JPG).")

    raw_bytes = await file.read()

    if plan_type in OCR_PLAN_TYPES:
        plan, report = _read_plan(raw_bytes, plan_type)
    elif plan_type in TAG_PLAN_TYPES:
        plan, report = _read_plumbing(raw_bytes, plan_type)
    else:
        plan, report = _detect_plan(raw_bytes, plan_type)

    estimate = estimate_plan(plan, load_catalog())
    # Assumptions are deliberately not surfaced in the UI, so the only place
    # they survive is the ledger. See app/audit.py.
    audit.record_estimate(plan_type, estimate, report, plan)

    return ImageEstimateResponse(extraction=report, estimate=estimate)


def _read_plan(raw_bytes: bytes, plan_type: str):
    """Floor plans: read the printed dimensions and derive geometry."""
    try:
        extraction = read_plan_bytes(raw_bytes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if not extraction.rooms_m or extraction.envelope_w_m <= 0 or extraction.envelope_l_m <= 0:
        raise HTTPException(
            422,
            {
                "message": (
                    "Could not read enough of the plan to estimate it. This path needs "
                    "printed room dimensions and margin dimension chains."
                ),
                "warnings": extraction.warnings(),
            },
        )

    return to_plan_schema(extraction, plan_type), report_from_extraction(extraction)


# A plan type can only be matched by references from its own trade. Asking
# whether ANY template exists is not enough: once the electrical crops were
# installed, a plumbing plan sailed past the guard and returned a cheerful
# 200 with a zero-peso estimate - which is precisely the "successful scan of
# a plan with no materials on it" the guard was added to prevent.
PLAN_TYPE_CATEGORY: dict[str, str] = {
    "Electrical Plan": "electrical",
    "Plumbing Plan": "plumbing",
}


def _templates_for(plan_type: str) -> dict[str, list[str]]:
    """Installed references whose SKU belongs to this plan type's trade."""
    category = PLAN_TYPE_CATEGORY.get(plan_type)
    if category is None:
        return {}
    catalog = load_catalog()
    return {
        item_id: files
        for item_id, files in templates_store.list_templates().items()
        if (catalog.get(item_id) or {}).get("category") == category
    }


def _read_plumbing(raw_bytes: bytes, plan_type: str):
    """Plumbing: count printed fixture tags, then derive what serves them.

    Not the detection path. The countable things on a sanitary plan - WC,
    LAV, FD - are written beside the fixture rather than drawn as a glyph,
    so there is nothing to template-match; and the fixtures themselves are
    client-supplied and never priced. What gets priced is the pipe and
    fittings the rules derive from the counts.
    """
    # Decoded plain, NOT through preprocess_image. Its denoise smooths small
    # glyphs: good for template matching, which wants clean edges, bad for a
    # text detector, which wants sharp strokes. Measured on 07.png the
    # preprocessed image reads 6 water closets against 8 plain.
    image = cv2.imdecode(np.frombuffer(raw_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Could not decode image - corrupt or unsupported format.")

    counts = tally(count_tags(read_tiled(image), FIXTURE_TAG_PATTERNS, image.shape))

    # A cleanout implies no materials, so a plan where only cleanouts were
    # read has produced nothing to price. Returning a cheerful zero there
    # is the same trap the empty-library guard exists to close.
    if not any(FIXTURE_PLUMBING.get(tag) for tag in counts):
        raise HTTPException(
            422,
            {
                "message": (
                    "No fixture tags could be read on this plumbing plan, so "
                    "there is nothing to derive pipework from. Tags like WC, "
                    "LAV and FD are small; a higher-resolution export of the "
                    "same drawing usually reads."
                ),
                "warnings": [f"read: {dict(counts)}" if counts else "read: nothing"],
            },
        )

    plan = PlanSchema(
        plan_type=plan_type, source="tags", fixture_tags=dict(counts)
    )
    # Nothing was measured, so there is no extraction report to give.
    return plan, None


def _detect_plan(raw_bytes: bytes, plan_type: str):
    """Electrical and plumbing: count symbols against uploaded references.

    Two ways this comes up empty, and NEITHER is a real zero. With no
    references nothing can match. And with references that match nothing,
    the reader has failed - every electrical plan has electrics, which is
    what makes it an electrical plan. An earlier version of this returned
    200 with a zero-peso estimate in the second case, on the reasoning that
    zero matches was a legitimate outcome. It is not: six of the eleven
    sample electrical plans came back as cheerful zeroes, which reads as
    "this building needs no wiring" rather than "I could not read it".
    """
    relevant = _templates_for(plan_type)
    if not relevant:
        raise HTTPException(
            422,
            f"No symbol references have been uploaded for a {plan_type}, so "
            f"nothing on it can be matched. Add a reference image for each "
            f"catalog item in the Symbol Library, then scan again.",
        )

    try:
        image = preprocess_image(raw_bytes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    detections = match_templates(image)
    plan = plan_from_detections(detections, plan_type)

    devices = sum(f.count for f in plan.fixtures)
    if plan.fixtures and devices < MIN_DEVICES:
        raise HTTPException(
            422,
            {
                "message": (
                    f"Only {devices} symbols on this {plan_type} matched a reference, "
                    f"too few to be a reading of the whole sheet. A drawing this "
                    f"sparse is usually a scan the matcher could not resolve - a "
                    f"higher-resolution export of the same sheet usually works."
                ),
                "warnings": [
                    f"{devices} devices matched, {MIN_DEVICES} is the minimum to price",
                    f"references available: {', '.join(sorted(relevant))}",
                ],
            },
        )

    if not plan.fixtures:
        raise HTTPException(
            422,
            {
                "message": (
                    f"No symbols on this {plan_type} matched any reference in the "
                    f"Symbol Library, so there is nothing to price. Either the "
                    f"drawing uses different symbols from the reference crops, or "
                    f"it is too small to match - a higher-resolution export of the "
                    f"same sheet usually works."
                ),
                "warnings": [
                    f"{len(detections)} raw detections, none of them a catalog item"
                    if detections
                    else "no symbol matched anywhere on the sheet",
                    f"references available: {', '.join(sorted(relevant))}",
                ],
            },
        )

    # Detection supplies counts only; there is nothing "read" to report on.
    return plan, None
