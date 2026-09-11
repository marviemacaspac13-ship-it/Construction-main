"""Derive a structural frame from a building envelope.

Everything else in the takeoff engine turns something that was *read* into
quantities. This module does not: no residential floor plan prints its
column schedule, and unlike a room dimension there is no printed text to
recover, so the frame is inferred from the envelope plus the sections in
EstimatingParams.

That makes every number here an assumption, and a consequential one -
concrete volume scales with the square of the column section, so a wrong
guess of 0.30 x 0.30 against a true 0.20 x 0.20 is 2.25x the cement.
Callers are expected to say so out loud; extract_plan raises a warning and
params.assumption_lines() states the sections used.

The eventual replacement is measurement, not a better guess: the black
squares on a CAD plan are the columns, and Scale.meters_per_pixel turns
their pixel size into a real section. This module is what stands in until
that exists.
"""

import math
from dataclasses import dataclass, field

from app.takeoff.constants import FRAME_MIX_CLASS, SLAB_MIX_CLASS
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import ConcreteElement


@dataclass
class FrameDerivation:
    """An assumed frame, with the workings kept so they can be reported."""

    column_count: int
    column_volume_m3: float
    footing_volume_m3: float
    slab_area_m2: float
    slab_volume_m3: float
    elements: list[ConcreteElement] = field(default_factory=list)

    @property
    def total_volume_m3(self) -> float:
        return self.column_volume_m3 + self.footing_volume_m3 + self.slab_volume_m3


def column_count(envelope_w_m: float, envelope_l_m: float, spacing_m: float) -> int:
    """Columns placed around the envelope at a given spacing.

    They sit on the perimeter, which is a closed loop, so the count is the
    perimeter divided by the spacing rather than that plus one. Four is the
    floor: a rectangular building has corners whatever its size.
    """
    perimeter = 2.0 * (envelope_w_m + envelope_l_m)
    if perimeter <= 0 or spacing_m <= 0:
        return 0
    return max(4, math.ceil(perimeter / spacing_m))


def derive_frame(
    envelope_w_m: float, envelope_l_m: float, params: EstimatingParams
) -> FrameDerivation | None:
    """Footings, columns and a slab on grade for a rectangular envelope.

    Returns None when there is nothing to stand on - no envelope, or the
    frame switched off - so that callers can tell "no concrete" apart from
    "zero concrete".

    Interior columns are not counted. A residential span is usually carried
    by the perimeter frame and the CHB walls, and inventing interior columns
    from an envelope alone would be guessing on top of guessing.
    """
    if not params.include_frame:
        return None
    if envelope_w_m <= 0 or envelope_l_m <= 0:
        return None

    count = column_count(envelope_w_m, envelope_l_m, params.column_spacing_m)

    # A column runs from its footing to the tie beam, which is close enough
    # to the wall height to use it rather than invent another knob.
    section_m2 = params.column_width_m * params.column_depth_m
    columns_m3 = count * section_m2 * params.default_wall_height_m

    # One isolated footing under each column.
    footings_m3 = (
        count
        * params.footing_width_m
        * params.footing_length_m
        * params.footing_thickness_m
    )

    # Slab on grade over the whole footprint. The envelope is a bounding
    # rectangle, so an L-shaped building takes more slab here than it pours.
    slab_area_m2 = envelope_w_m * envelope_l_m
    slab_m3 = slab_area_m2 * params.slab_thickness_m

    elements: list[ConcreteElement] = []
    if footings_m3 > 0:
        elements.append(
            ConcreteElement(
                id="footings",
                kind="footing",
                volume_m3=footings_m3,
                mix_class=FRAME_MIX_CLASS,
            )
        )
    if columns_m3 > 0:
        elements.append(
            ConcreteElement(
                id="columns",
                kind="column",
                volume_m3=columns_m3,
                mix_class=FRAME_MIX_CLASS,
            )
        )
    if slab_m3 > 0:
        elements.append(
            ConcreteElement(
                id="slab_on_grade",
                kind="slab",
                volume_m3=slab_m3,
                mix_class=SLAB_MIX_CLASS,
            )
        )

    return FrameDerivation(
        column_count=count,
        column_volume_m3=columns_m3,
        footing_volume_m3=footings_m3,
        slab_area_m2=slab_area_m2,
        slab_volume_m3=slab_m3,
        elements=elements,
    )
