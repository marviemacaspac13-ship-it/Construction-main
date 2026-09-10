"""Assemble a validated extraction into the PlanSchema the rules consume."""

from dataclasses import dataclass, field

from app.extract.chains import ChainCheck, confidence_from_checks, validate_chain
from app.extract.geometry import AreaCheck, WallDerivation, check_area, derive_walls
from app.extract.tokens import RoomToken, count_openings, parse_rooms
from app.extract.units_infer import UnitInference, infer_units
from app.takeoff.constants import DEFAULT_DOOR_M, DEFAULT_WINDOW_M
from app.takeoff.schema import Opening, PlanSchema, PlanType, Room, Wall

# Philippine residential practice: exterior walls 6", interior partitions 4".
EXTERIOR_THICKNESS = "6in"
INTERIOR_THICKNESS = "4in"


@dataclass
class PlanExtraction:
    """Everything read off one plan, in metres, with its own quality report."""

    envelope_w_m: float
    envelope_l_m: float
    rooms_m: list[RoomToken]
    units: UnitInference
    chain_checks: list[ChainCheck] = field(default_factory=list)
    doors: int = 0
    windows: int = 0
    walls: WallDerivation | None = None
    area: AreaCheck | None = None

    @property
    def chain_confidence(self) -> float:
        return confidence_from_checks(self.chain_checks)

    @property
    def confidence(self) -> float:
        """Combined confidence: unit inference and chain checksums."""
        return round(min(self.units.confidence, 1.0) * self.chain_confidence, 3)

    def warnings(self) -> list[str]:
        out: list[str] = []
        if self.units.confidence < 0.5:
            out.append(f"Unit inference weak: {self.units.note}")
        for i, check in enumerate(self.chain_checks):
            if not check.ok:
                out.append(
                    f"Dimension chain {i + 1} does not close: segments sum to "
                    f"{check.total:g} against a stated {check.stated_total:g} "
                    f"(off by {check.error:+g}) - likely a misread digit."
                )
        if self.area is not None and self.area.accounted_ratio > 1.05:
            out.append(
                f"Labelled rooms plus walls cover {self.area.accounted_ratio:.0%} of "
                f"the envelope - more than the whole building. The envelope was read "
                f"too small, or a room was counted twice."
            )
        if self.area is not None and self.area.accounted_ratio < 0.70:
            out.append(
                f"Only {self.area.accounted_ratio:.0%} of the envelope is accounted "
                f"for by labelled rooms plus walls ({self.area.unaccounted_m2:g} m^2 "
                f"unexplained) - rooms may have been missed, or the plan has "
                f"unlabelled circulation."
            )
        # A building with rooms necessarily has doors, and almost certainly
        # windows. Reading none means the schedule tags were missed, which
        # silently inflates the estimate - no opening is deducted from the
        # masonry. This is the one error mode the chain checksums cannot see.
        if len(self.rooms_m) >= 2 and self.doors == 0:
            out.append(
                f"{len(self.rooms_m)} rooms but no door tags were read. No openings "
                f"are being deducted, so masonry is over-estimated."
            )
        elif len(self.rooms_m) >= 3 and self.windows == 0:
            out.append(
                f"{len(self.rooms_m)} rooms but no window tags were read; masonry is "
                f"over-estimated by whatever the windows would have deducted."
            )
        if not self.rooms_m:
            out.append("No room dimensions were read; wall lengths cannot be derived.")
        return out


def extract_plan(
    envelope_w: float,
    envelope_l: float,
    room_blocks: list[str],
    chains: list[tuple[list[float], float]] | None = None,
    opening_tags: list[str] | None = None,
) -> PlanExtraction:
    """Turn raw text read off a plan into a validated, metric extraction.

    envelope_w/envelope_l and the chain values are in the drawing's own
    units; the unit inference converts everything to metres.
    """
    units = infer_units(max(envelope_w, envelope_l))

    checks = [validate_chain(values, total) for values, total in (chains or [])]

    raw_rooms = parse_rooms(room_blocks)
    rooms_m = [
        RoomToken(
            name=room.name,
            width=units.to_metres(room.width),
            length=units.to_metres(room.length),
        )
        for room in raw_rooms
    ]

    w_m = units.to_metres(envelope_w)
    l_m = units.to_metres(envelope_l)

    openings = count_openings(opening_tags or [])

    extraction = PlanExtraction(
        envelope_w_m=w_m,
        envelope_l_m=l_m,
        rooms_m=rooms_m,
        units=units,
        chain_checks=checks,
        doors=openings["door"],
        windows=openings["window"],
    )
    extraction.walls = derive_walls(rooms_m, w_m, l_m)
    extraction.area = check_area(rooms_m, w_m, l_m, extraction.walls.total_m)
    return extraction


def to_plan_schema(
    extraction: PlanExtraction, plan_type: PlanType = "Floor Plan"
) -> PlanSchema:
    """Project a validated extraction onto the rule engine's input record.

    Openings are placed where they physically sit: windows in exterior
    walls, doors in interior partitions.
    """
    walls: list[Wall] = []
    derivation = extraction.walls
    if derivation is None:  # pragma: no cover - extract_plan always sets it
        raise ValueError("extraction has no wall derivation")

    if derivation.exterior_m > 0:
        window_openings = (
            [
                Opening(
                    kind="window",
                    width_m=DEFAULT_WINDOW_M[0],
                    height_m=DEFAULT_WINDOW_M[1],
                    count=extraction.windows,
                )
            ]
            if extraction.windows
            else []
        )
        walls.append(
            Wall(
                id="exterior",
                length_m=derivation.exterior_m,
                thickness=EXTERIOR_THICKNESS,
                openings=window_openings,
            )
        )

    if derivation.interior_m > 0:
        door_openings = (
            [
                Opening(
                    kind="door",
                    width_m=DEFAULT_DOOR_M[0],
                    height_m=DEFAULT_DOOR_M[1],
                    count=extraction.doors,
                )
            ]
            if extraction.doors
            else []
        )
        walls.append(
            Wall(
                id="interior",
                length_m=derivation.interior_m,
                thickness=INTERIOR_THICKNESS,
                openings=door_openings,
            )
        )

    rooms = [
        Room(
            id=f"r{i + 1}",
            name=room.name,
            area_m2=room.area,
            width_m=room.width,
            length_m=room.length,
        )
        for i, room in enumerate(extraction.rooms_m)
        if room.area > 0
    ]

    return PlanSchema(plan_type=plan_type, source="ocr", walls=walls, rooms=rooms)
