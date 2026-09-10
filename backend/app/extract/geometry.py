"""Deriving wall quantities from printed room dimensions.

No pixel measurement and no wall tracing. Each interior wall borders two
rooms and each exterior wall borders one, so:

    sum of room perimeters = 2 x interior + 1 x exterior
    => total wall = (sum of room perimeters + exterior perimeter) / 2

The same room dimensions give an area cross-check: rooms plus wall
footprint should account for most of the envelope. A large shortfall means
rooms were missed by the reader, or the plan has unlabelled circulation.
"""

from dataclasses import dataclass

from app.extract.tokens import RoomToken


@dataclass(frozen=True)
class WallDerivation:
    exterior_m: float
    interior_m: float
    total_m: float
    room_perimeter_sum_m: float


def envelope_perimeter_m(width_m: float, length_m: float) -> float:
    return 2.0 * (width_m + length_m)


def derive_walls(
    rooms_m: list[RoomToken],
    envelope_w_m: float,
    envelope_l_m: float,
) -> WallDerivation:
    """Total wall length from room perimeters plus the envelope."""
    exterior = envelope_perimeter_m(envelope_w_m, envelope_l_m)
    perimeter_sum = sum(room.perimeter for room in rooms_m)
    interior = max(0.0, (perimeter_sum - exterior) / 2.0)
    return WallDerivation(
        exterior_m=exterior,
        interior_m=interior,
        total_m=exterior + interior,
        room_perimeter_sum_m=perimeter_sum,
    )


@dataclass(frozen=True)
class AreaCheck:
    room_area_m2: float
    envelope_area_m2: float
    wall_footprint_m2: float
    accounted_ratio: float
    unaccounted_m2: float


def check_area(
    rooms_m: list[RoomToken],
    envelope_w_m: float,
    envelope_l_m: float,
    total_wall_m: float,
    wall_thickness_m: float = 0.20,
) -> AreaCheck:
    """How much of the envelope the labelled rooms account for."""
    room_area = sum(room.area for room in rooms_m)
    envelope_area = envelope_w_m * envelope_l_m
    footprint = total_wall_m * wall_thickness_m
    accounted = room_area + footprint
    ratio = accounted / envelope_area if envelope_area else 0.0
    return AreaCheck(
        room_area_m2=room_area,
        envelope_area_m2=envelope_area,
        wall_footprint_m2=footprint,
        accounted_ratio=round(ratio, 4),
        unaccounted_m2=round(envelope_area - accounted, 2),
    )
