from dotenv import load_dotenv
load_dotenv()

import traceback
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.vision.preprocess import preprocess_image
from app.vision.template_match import match_templates
from app.pricing import price_takeoff
from app.schemas import ScanResponse
from app.materials import load_catalog
from app import templates_store

from pydantic import BaseModel

from app.extract.reader import read_plan_bytes
from app.extract.report import ImageEstimateResponse, report_from_extraction
from app.extract.to_plan import to_plan_schema
from app.takeoff.estimator import EstimateResponse, estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import PlanSchema

# Reading geometry off an image currently works for floor plans only:
# the extractor derives walls from printed room dimensions. Electrical and
# plumbing plans need symbol detection, which is a different path.
IMAGE_ESTIMATE_PLAN_TYPES = ("Floor Plan",)


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
    if plan_type not in IMAGE_ESTIMATE_PLAN_TYPES:
        raise HTTPException(
            422,
            f"Image estimating supports {' / '.join(IMAGE_ESTIMATE_PLAN_TYPES)} only. "
            f"A '{plan_type}' needs symbol detection, which requires reference images "
            f"uploaded in the Symbol Library.",
        )

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file (PNG/JPG).")

    raw_bytes = await file.read()
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

    plan = to_plan_schema(extraction, plan_type)
    return ImageEstimateResponse(
        extraction=report_from_extraction(extraction),
        estimate=estimate_plan(plan, load_catalog()),
    )
