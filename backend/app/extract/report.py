"""API-facing view of an extraction.

PlanExtraction is a working dataclass full of internal objects. This is
the flattened, serialisable version the frontend needs: what was read,
how much of it checks out, and what the reader is unsure about.
"""

from pydantic import BaseModel, Field

from app.extract.to_plan import PlanExtraction
from app.takeoff.estimator import EstimateResponse
from app.takeoff.contracts import EstimateInputSnapshot, ScanMetadata
from app.schemas import Detection


class ChainReport(BaseModel):
    segments: list[float]
    total: float
    stated_total: float
    ok: bool
    error: float


class RoomReport(BaseModel):
    name: str
    width_m: float
    length_m: float
    area_m2: float


class ExtractionReport(BaseModel):
    """What the reader saw, and how confident it is about it."""

    unit: str
    unit_note: str
    envelope_w_m: float
    envelope_l_m: float
    envelope_area_m2: float
    rooms: list[RoomReport]
    room_area_m2: float
    area_accounted_ratio: float
    exterior_wall_m: float
    interior_wall_m: float
    total_wall_m: float
    doors: int
    windows: int
    # Concrete is derived from the envelope and the assumed sections. Null
    # means no frame was derived at all. The column COUNT is read off the
    # drawing where it draws them; columns_counted says whether it was.
    column_count: int | None = None
    columns_counted: bool = False
    concrete_volume_m3: float | None = None
    chains: list[ChainReport]
    confidence: float
    warnings: list[str] = Field(default_factory=list)


class ImageEstimateResponse(BaseModel):
    """Additive scan response, retaining exact inputs for later corrections.

    `extraction` is a floor-plan report; tags and detections still return
    null there. Unpriced BOM lines remain in `estimate.unpriced`.
    """

    extraction: ExtractionReport | None
    estimate: EstimateResponse
    original_input: EstimateInputSnapshot
    scan: ScanMetadata
    unmatched_detections: list[Detection] = Field(default_factory=list)
    # HMAC over original_input for this user and image; the save checks it, so
    # the stored "original read" is what the scanner produced.
    input_signature: str | None = None


def report_from_extraction(extraction: PlanExtraction) -> ExtractionReport:
    walls = extraction.walls
    area = extraction.area
    return ExtractionReport(
        unit=extraction.units.unit,
        unit_note=extraction.units.note,
        envelope_w_m=round(extraction.envelope_w_m, 3),
        envelope_l_m=round(extraction.envelope_l_m, 3),
        envelope_area_m2=round(area.envelope_area_m2, 2) if area else 0.0,
        rooms=[
            RoomReport(
                name=room.name,
                width_m=round(room.width, 3),
                length_m=round(room.length, 3),
                area_m2=round(room.area, 3),
            )
            for room in extraction.rooms_m
        ],
        room_area_m2=round(area.room_area_m2, 2) if area else 0.0,
        area_accounted_ratio=area.accounted_ratio if area else 0.0,
        exterior_wall_m=round(walls.exterior_m, 3) if walls else 0.0,
        interior_wall_m=round(walls.interior_m, 3) if walls else 0.0,
        total_wall_m=round(walls.total_m, 3) if walls else 0.0,
        doors=extraction.doors,
        windows=extraction.windows,
        column_count=extraction.frame.column_count if extraction.frame else None,
        columns_counted=bool(extraction.frame and extraction.frame.columns_counted),
        concrete_volume_m3=(
            round(extraction.frame.total_volume_m3, 2) if extraction.frame else None
        ),
        chains=[
            ChainReport(
                segments=check.kept,
                total=check.total,
                stated_total=check.stated_total,
                ok=check.ok,
                error=check.error,
            )
            for check in extraction.chain_checks
        ],
        confidence=extraction.confidence,
        warnings=extraction.warnings(),
    )
