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

The replacement is measurement, not a better guess, and it has begun: the
black squares on a CAD plan are the columns, and app.extract.columns
counts them. Where a plausible count is passed in, it sets how many
columns and footings there are - interior ones included - and the spacing
assumption stands down. Their SECTION is still the guide constant; sizing
them needs the ruler in scale.py, which is not yet trusted.
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
    # The columns were counted on the drawing, not placed at a spacing.
    columns_counted: bool = False

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


# A drawn count is trusted only near what the envelope implies. Far below
# means the sheet does not draw its columns - a hand sketch or a scan finds
# 0-2 - and far above means something else on the sheet is solid and square.
# Either is a failed detection, not a discovery about the building. The two
# CAD plans sit at 1.07 (16 vs 15) and 0.77 (10 vs 13).
PLAUSIBLE_COLUMNS_LOW, PLAUSIBLE_COLUMNS_HIGH = 0.5, 1.5


def plausible_column_count(
    counted: int, envelope_w_m: float, envelope_l_m: float, spacing_m: float
) -> bool:
    """Whether a count of drawn columns is close enough to be believed."""
    expected = column_count(envelope_w_m, envelope_l_m, spacing_m)
    if counted < 4 or expected == 0:
        return False
    return PLAUSIBLE_COLUMNS_LOW * expected <= counted <= PLAUSIBLE_COLUMNS_HIGH * expected


def derive_frame(
    envelope_w_m: float,
    envelope_l_m: float,
    params: EstimatingParams,
    drawn_columns: int | None = None,
) -> FrameDerivation | None:
    """Footings, columns and a slab on grade for a rectangular envelope.

    Returns None when there is nothing to stand on - no envelope, or the
    frame switched off - so that callers can tell "no concrete" apart from
    "zero concrete".

    `drawn_columns` is the number of columns counted on the drawing. It is
    used when it is plausible for the envelope, and it includes interior
    columns. Otherwise - hand sketches and scans draw none - columns are
    placed round the perimeter at `column_spacing_m`, and interior ones are
    NOT invented: guessing them from an envelope alone would be guessing on
    top of guessing.
    """
    if not params.include_frame:
        return None
    if envelope_w_m <= 0 or envelope_l_m <= 0:
        return None

    counted = drawn_columns is not None and plausible_column_count(
        drawn_columns, envelope_w_m, envelope_l_m, params.column_spacing_m
    )
    count = (
        drawn_columns
        if counted
        else column_count(envelope_w_m, envelope_l_m, params.column_spacing_m)
    )
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
                counted=counted,
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
                counted=counted,
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
        columns_counted=counted,
    )
