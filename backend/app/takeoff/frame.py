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

from app.takeoff.constants import (
    BEAM_SECTION_M,
    COLUMN_SECTION_M,
    COLUMN_STANDARD_HEIGHT_M,
    FOOTING_SIDE_M,
    FRAME_MIX_CLASS,
    SLAB_MIX_CLASS,
)
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
    beam_length_m: float = 0.0
    beam_volume_m3: float = 0.0
    elements: list[ConcreteElement] = field(default_factory=list)

    @property
    def total_volume_m3(self) -> float:
        return (
            self.column_volume_m3
            + self.footing_volume_m3
            + self.slab_volume_m3
            + self.beam_volume_m3
        )


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
    perimeter_m = 2.0 * (envelope_w_m + envelope_l_m)

    # Sections and the column height are the guide standard, not knobs.
    col_w, col_d = COLUMN_SECTION_M
    columns_m3 = count * col_w * col_d * COLUMN_STANDARD_HEIGHT_M

    # One square footing under each column, sized by the guide bar schedule.
    # Its thickness is the one dimension the guide never gives.
    footings_m3 = count * FOOTING_SIDE_M * FOOTING_SIDE_M * params.footing_thickness_m

    # Slab on grade over the whole footprint. The envelope is a bounding
    # rectangle, so an L-shaped building takes more slab here than it pours.
    slab_area_m2 = envelope_w_m * envelope_l_m
    slab_m3 = slab_area_m2 * params.slab_thickness_m

    # A tie beam round the perimeter. The guide specifies beams in full but
    # not where they run, so this is the assumption, not the section.
    beam_w, beam_d = BEAM_SECTION_M
    beam_length_m = perimeter_m if params.include_perimeter_beam else 0.0
    beams_m3 = beam_length_m * beam_w * beam_d

    elements: list[ConcreteElement] = []
    if footings_m3 > 0:
        elements.append(
            ConcreteElement(
                id="footings",
                kind="footing",
                volume_m3=footings_m3,
                mix_class=FRAME_MIX_CLASS,
                count=count,
                width_m=FOOTING_SIDE_M,
                length_m=FOOTING_SIDE_M,
                height_m=params.footing_thickness_m,
            )
        )
    if columns_m3 > 0:
        elements.append(
            ConcreteElement(
                id="columns",
                kind="column",
                volume_m3=columns_m3,
                mix_class=FRAME_MIX_CLASS,
                count=count,
                width_m=col_w,
                length_m=col_d,
                height_m=COLUMN_STANDARD_HEIGHT_M,
            )
        )
    if beams_m3 > 0:
        elements.append(
            ConcreteElement(
                id="perimeter_beam",
                kind="beam",
                volume_m3=beams_m3,
                mix_class=FRAME_MIX_CLASS,
                count=1,
                width_m=beam_w,
                length_m=beam_length_m,
                height_m=beam_d,
            )
        )
    if slab_m3 > 0:
        elements.append(
            ConcreteElement(
                id="slab_on_grade",
                kind="slab",
                volume_m3=slab_m3,
                mix_class=SLAB_MIX_CLASS,
                count=1,
                width_m=envelope_w_m,
                length_m=envelope_l_m,
                height_m=params.slab_thickness_m,
            )
        )

    return FrameDerivation(
        column_count=count,
        column_volume_m3=columns_m3,
        footing_volume_m3=footings_m3,
        slab_area_m2=slab_area_m2,
        slab_volume_m3=slab_m3,
        beam_length_m=beam_length_m,
        beam_volume_m3=beams_m3,
        elements=elements,
    )
