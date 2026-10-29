from dotenv import load_dotenv
load_dotenv()

import traceback
import hashlib
import asyncio

import cv2
import numpy as np
from fastapi import Depends, FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.vision.preprocess import preprocess_image
from app.vision.relabel import relabel_from_adjacent_text
from app.vision.template_match import match_templates
from app.pricing import price_takeoff
from app.schemas import ScanResponse
from app.materials import load_catalog
from app import audit, templates_store
from app.auth import current_user
from app.revisions import router as revisions_router, sign_original_input
from app.plan_assets import MAX_BYTES as MAX_PLAN_BYTES, inspect_image, router as plan_assets_router
from app.corrections import router as corrections_router
from app.editor import router as editor_router
from app import plumbing_vision
from app import electrical_review as electrical_boundary
from app import electrical_vision
from app.electrical_models import ElectricalObservation
from app.extract.tags import count_tags, read_tiled, tally
from app.takeoff.constants import FIXTURE_PLUMBING, FIXTURE_TAG_PATTERNS, MIN_FIXTURES

from pydantic import BaseModel

from app.extract.reader import read_plan_bytes
from app.extract.report import ImageEstimateResponse, report_from_extraction
from app.extract.to_plan import to_plan_schema
from app.takeoff.from_detections import plan_from_detections
from app.takeoff.estimator import EstimateResponse, estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import FixtureTagObservation, PlanSchema
from app.takeoff.contracts import EstimateInputSnapshot, ScanMetadata, snapshot_catalog
from app.takeoff.units import UNIT_SPECS

VALID_PLAN_TYPES = ("Floor Plan", "Electrical Plan", "Plumbing Plan")

# Floor plans carry printed room dimensions, so they are read. Electrical
# and plumbing plans do not - their quantities are discrete symbols, so
# they are detected against uploaded references. Both paths end in the same
# PlanSchema and the same rule engine.
OCR_PLAN_TYPES = ("Floor Plan",)
# Read by counting printed tags rather than by matching symbols.
TAG_PLAN_TYPES = ("Plumbing Plan",)

# The fewest material-bearing fixtures a real sanitary layout can carry: a
# water closet, a lavatory and a floor drain. Below that the reader has
# found a fragment, not a plan - measured across the sample sheets, the one
# that reads gives 33 and the two that do not give 1 each, so the floor sits
# in a wide gap rather than on a cliff.
#
# The trade-off is deliberate and worth knowing: a sheet drawn for a real
# two-fixture powder room would now be refused. Refusing a small real plan
# is recoverable - the message says why and names what was read. Pricing a
# misread one is not, because nothing downstream can tell that P1,744 came
# from a single stray tag.
# OFF by default, and the measurement is why.
#
# Re-reading an electrical sheet as text to identify labelled symbols takes
# a scan from ~4s to ~19s - the tiled read is 25 OCR passes - and buys, on
# this corpus, exactly one rename: the single ACU on 05.png, worth P17 of a
# P21,624 estimate. 0.08% for a 5x slowdown.
#
# There is no cheaper version. A 3x3 tile grid misses the ACU, 4x4 finds it
# at 8s but sits right at the edge, and a crop around each detection works
# only between 0.10 and 0.15 of the sheet and fails either side. Every
# route is a narrow band on one sample.
#
# Set True where a drawing labels its symbol variants in quantity. The
# machinery and its tests stay because the mechanism is correct and the
# trap it avoids is worth not rediscovering - see app/vision/relabel.py.
READ_SYMBOL_LABELS = False

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
app.include_router(revisions_router)
app.include_router(plan_assets_router)
app.include_router(corrections_router)
app.include_router(editor_router)
app.include_router(plumbing_vision.router)

# Every route but /health needs a signed-in user - see app/auth.py.
SIGNED_IN = [Depends(current_user)]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # The traceback goes to the server log; the browser gets no internals,
    # which once included catalog keys and the Supabase project address.
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on the server. Try again; if it keeps "
                           "happening, the details are in the backend log."},
        headers={"Access-Control-Allow-Origin": "http://localhost:5173"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/scan", response_model=ScanResponse, dependencies=SIGNED_IN)
def scan_plan(file: UploadFile = File(...)):
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

    raw_bytes = file.file.read(MAX_PLAN_BYTES + 1)
    inspect_image(raw_bytes, file.filename or '', file.content_type)
    image = preprocess_image(raw_bytes)
    detections = match_templates(image)
    return price_takeoff(detections)

@app.get("/api/materials", dependencies=SIGNED_IN)
def list_materials():
    return list(load_catalog().values())

@app.post("/api/templates", dependencies=SIGNED_IN)
def upload_template(item_id: str = Form(...), file: UploadFile = File(...)):
    catalog = load_catalog()
    if item_id not in catalog:
        raise HTTPException(400, f"'{item_id}' is not a known catalog item_id.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file (PNG/JPG).")

    raw_bytes = file.file.read()
    try:
        filename = templates_store.save_template(
            item_id, raw_bytes, file.filename or "template.png"
        )
    except templates_store.UnsafeTemplatePath as exc:
        raise HTTPException(400, str(exc))
    return {"item_id": item_id, "filename": filename}


@app.get("/api/templates", dependencies=SIGNED_IN)
def get_templates():
    return templates_store.list_templates()

@app.delete("/api/templates/{item_id}/{filename}", dependencies=SIGNED_IN)
def remove_template(item_id: str, filename: str):
    # The store refuses any name that is not a plain single segment, so a
    # crafted path cannot reach a file outside the template directory.
    try:
        deleted = templates_store.delete_template(item_id, filename)
    except templates_store.UnsafeTemplatePath as exc:
        raise HTTPException(400, str(exc))
    if not deleted:
        raise HTTPException(404, "Template not found.")
    return {"deleted": True}

@app.post("/api/estimate", response_model=EstimateResponse, dependencies=SIGNED_IN)
def estimate(request: EstimateRequest):
    """Price an already-structured plan description.

    Independent of how the plan was described - a form, OCR, detection, or
    a CAD parser all produce the same PlanSchema.
    """
    return estimate_plan(request.plan, load_catalog(), request.params)


@app.post('/api/electrical/proposals', dependencies=SIGNED_IN)
async def electrical_proposals(file: UploadFile = File(...), owner: str = Depends(current_user)):
    """Gemini proposals first; local detection is automatic, with the same review scope."""
    raw = await file.read(MAX_PLAN_BYTES + 1)
    metadata = inspect_image(raw, file.filename or '', file.content_type or '')
    proposed = await electrical_vision.find_proposals(raw,metadata,owner)
    if proposed['available']:
        return proposed
    return await asyncio.to_thread(_local_electrical_proposals,raw,metadata,owner,
        proposed['attempts'],proposed['message'])


def _local_electrical_proposals(raw, metadata, owner, attempts, message):
    """Keep installed local detection as fallback; never merge two inventories."""
    image = preprocess_image(raw)
    h, w = image.shape[:2]
    observations = []
    for detection in match_templates(image):
        family = ('light_point' if detection.label.startswith('CLR') else
                  'convenience_outlet' if detection.label.startswith('OT') else 'unknown')
        if family == 'unknown':
            continue
        x1, y1, x2, y2 = detection.bbox
        identifier = f'proposal-{len(observations)+1}'
        observations.append(ElectricalObservation(id=identifier, assembly_id=identifier,
            box_2d=[y1/h*1000, x1/w*1000, min(y2/h*1000,1000), min(x2/w*1000,1000)],
            device_class=family, socket_configuration='duplex' if family == 'convenience_outlet' else None,
            uncertainty='Template family proposal; verify location and product against the drawing.'))
        if len(observations) > 500:
            raise HTTPException(422, 'More than 500 proposals. Upload a smaller plan section.')
    limitations=['Local symbol proposals can miss devices and include false matches. Check the entire drawing.',
        'Local fallback does not automatically recognize switches. Add missed switches and classify them; unsupported types require explicit exclusion.',
        'Device and box pricing remains partial. Circuit materials are excluded.']
    try:
        receipt = electrical_boundary.issue_review(raw, owner, observations, provider='template', model='local-symbol-library',
            attempts=attempts,limitations=limitations)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return dict(source_sha256=metadata['source_sha256'], image_width=w, image_height=h,
        available=True,provider='template',model='local-symbol-library',attempts=attempts,
        proposed=observations, receipt=receipt,message=message,limitations=limitations)


@app.post("/api/estimate/image", response_model=ImageEstimateResponse, dependencies=SIGNED_IN)
def estimate_image(
    file: UploadFile = File(...),
    plan_type: str = Form("Floor Plan"),
    wall_height_m: float | None = Form(None, gt=0, le=10),
    fixture_review: str | None = Form(None, max_length=800_000),
    electrical_review: str | None = Form(None, max_length=2_000_000),
    owner: str = Depends(current_user),
):
    """Read and price a plan; floor plans accept one project-wide wall height.

    Returns the estimate alongside what the reader saw and how much of it
    checks out, so a low-confidence result is visible rather than implied.
    """
    if plan_type not in VALID_PLAN_TYPES:
        raise HTTPException(
            422,
            f"Unknown plan type '{plan_type}'. Expected one of: "
            f"{', '.join(VALID_PLAN_TYPES)}.",
        )

    if wall_height_m is not None and plan_type not in OCR_PLAN_TYPES:
        raise HTTPException(422, "Wall height applies only to Floor Plan estimates.")
    if fixture_review is not None and plan_type not in TAG_PLAN_TYPES:
        raise HTTPException(422, "Fixture review applies only to plumbing plans.")
    if electrical_review is not None and plan_type != 'Electrical Plan':
        raise HTTPException(422, 'Electrical review applies only to electrical plans.')

    # Resolve once, before recognition. The same value prices walls and is
    # captured for replay; structural member dimensions remain independent.
    params = EstimatingParams(**(
        {"default_wall_height_m": wall_height_m} if wall_height_m is not None else {}
    ))

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file (PNG/JPG).")

    raw_bytes = file.file.read(MAX_PLAN_BYTES + 1)
    inspect_image(raw_bytes, file.filename or '', file.content_type)

    unmatched = []
    if plan_type in OCR_PLAN_TYPES:
        plan, report = _read_plan(raw_bytes, plan_type)
    elif plan_type in TAG_PLAN_TYPES:
        review = plumbing_vision.validate_review(fixture_review, raw_bytes, owner) if fixture_review else None
        plan, report = _read_plumbing(raw_bytes, plan_type, review) if review else _read_plumbing(raw_bytes, plan_type)
    elif electrical_review is not None:
        try:
            from app.electrical_models import ElectricalReviewSubmission
            submission = ElectricalReviewSubmission.model_validate_json(electrical_review)
            if submission.estimate_scope not in ('devices_and_boxes', 'reviewed_device_allowances'):
                raise ValueError('This workflow requires explicit reviewed electrical estimate scope.')
            review = electrical_boundary.confirm_review(submission, raw_bytes, owner)
            plan, report = electrical_boundary.reviewed_plan(review), None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    else:
        plan, report, unmatched = _detect_plan(raw_bytes, plan_type)

    catalog = load_catalog()
    estimate = estimate_plan(plan, catalog, params)
    # Assumptions are deliberately not surfaced in the UI, so the only place
    # they survive is the ledger. See app/audit.py.
    audit.record_estimate(plan_type, estimate, report, plan)

    original_input = EstimateInputSnapshot(
        plan=plan, params=params, prices=snapshot_catalog(catalog, estimate.priced_at),
    )
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return ImageEstimateResponse(
        extraction=report, estimate=estimate, original_input=original_input,
        scan=ScanMetadata(source_sha256=source_sha256, method=plan.source),
        unmatched_detections=unmatched,
        input_signature=sign_original_input(original_input, source_sha256, owner),
    )


def _read_plan(raw_bytes: bytes, plan_type: str):
    """Floor plans: read the printed dimensions and derive geometry."""
    try:
        extraction = read_plan_bytes(raw_bytes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if not extraction.rooms_m or extraction.envelope_w_m <= 0 or extraction.envelope_l_m <= 0:
        # Name the cause where it is knowable. A sheet dimensioned in feet
        # and inches cannot be read at all - the notation never parses into
        # a dimension, which is why it fails safely - and telling someone
        # only that the plan "could not be read" sends them looking for a
        # better scan of a drawing that was never going to work.
        if extraction.looks_imperial:
            message = (
                "This plan is dimensioned in feet and inches. TRACE reads metric "
                "drawings - millimetres, centimetres or metres - and prices them "
                "against a Philippine catalog, so an imperial plan cannot be "
                "estimated. Nothing was guessed."
            )
        else:
            message = (
                "Could not read enough of the plan to estimate it. This path needs "
                "printed room dimensions and margin dimension chains."
            )
        raise HTTPException(422, {"message": message, "warnings": extraction.warnings()})

    # No margin chain read means the outline rests on numbers nothing checks.
    # On the shrunk sample plans every such read priced the building at 1.6x
    # to 2.7x its full-size total. See tests/test_floor_needs_a_chain.py.
    if not extraction.chain_checks:
        raise HTTPException(422, {
            "message": (
                "Could not read the plan's dimension lines clearly enough to check "
                "the building size, so it was not priced. Upload the original export "
                "of the drawing; enlarging a small screenshot does not restore "
                "missing detail."
            ),
            "warnings": extraction.warnings(),
        })

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


def _read_plumbing(raw_bytes: bytes, plan_type: str, review=None):
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

    # A confirmed tag review already replaces every tag class, so reading the
    # sheet again would cost the whole tiled OCR pass for nothing.
    tags_reviewed = review is not None and review.provider == "tags"
    tag_counts = {} if tags_reviewed else count_tags(read_tiled(image), FIXTURE_TAG_PATTERNS, image.shape)
    counts = tally(tag_counts)
    observations = [
        FixtureTagObservation(
            tag=tag,
            x_px=box.cx,
            y_px=box.cy,
            score=box.score,
        )
        for tag, tag_count in tag_counts.items()
        for box in tag_count.boxes
    ]

    # A cleanout implies no materials, so it does not count towards the
    # floor below - a sheet where only cleanouts were read has produced
    # nothing to price.
    if review is not None:
        counts, observations = plumbing_vision.apply_review(counts, observations, review)
    fixtures = sum(n for tag, n in counts.items() if FIXTURE_PLUMBING.get(tag))

    # Nothing read at all. The same trap the empty-library guard closes.
    if fixtures == 0:
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

    # Something read, but too little to be a whole layout. This is the
    # plumbing half of MIN_DEVICES, and it was missing for as long as the
    # electrical one existed: two sample sheets were pricing a single stray
    # tag at P1,744 apiece, which is the "empty result is never a real zero"
    # failure wearing a small non-zero number instead.
    if fixtures < MIN_FIXTURES and (review is None or not review.accepted):
        raise HTTPException(
            422,
            {
                "message": (
                    f"Only {fixtures} plumbing fixture"
                    f"{'' if fixtures == 1 else 's'} could be read on this "
                    f"plan, too few to be a whole sanitary layout. The tags "
                    f"are probably drawn differently here, or are too small "
                    f"to resolve - a higher-resolution export of the same "
                    f"drawing usually reads."
                ),
                "warnings": [
                    f"read: {dict(counts)}",
                    f"{fixtures} fixtures imply materials, {MIN_FIXTURES} is the minimum to price",
                ],
            },
        )

    plan = PlanSchema(
        plan_type=plan_type,
        source="tags",
        fixture_tags=dict(counts),
        fixture_tag_observations=observations,
        fixture_review=review,
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

    # A drawing puts the same circle on a general-purpose outlet and an AC
    # outlet, and writes the difference beside it. Reading that word is the
    # only way to tell them apart, so the sheet is read again as TEXT and
    # any whitelisted word renames the symbol it sits next to.
    #
    # Read plain and tiled, for two separate reasons. Plain because the
    # denoise in preprocess_image smooths small glyphs - good for shape
    # matching, bad for a text detector. Tiled because a whole-page pass
    # does not find the ACU at all (24 boxes, none of them it) while a 5x5
    # tiled pass does. A crop around each detection was measured too: it
    # works at 0.10 of the sheet and fails at both 0.06 and 0.20, a band too
    # narrow to trust across images that run from 0.16 to 3.15 MP.
    #
    # It costs about 11s on a 0.32 MP sheet, which makes this the slowest
    # path in the app. That is a real price for a small correction, and the
    # reason it is worth paying is that a mislabelled symbol is wrong in a
    # way no reviewer can see: the count is right, the total is plausible,
    # and only the line item is false.
    if READ_SYMBOL_LABELS:
        plain = cv2.imdecode(np.frombuffer(raw_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if plain is not None:
            detections = relabel_from_adjacent_text(
                detections, read_tiled(plain), plain.shape
            )

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
    return plan, None, [d for d in detections if d.label not in UNIT_SPECS]
