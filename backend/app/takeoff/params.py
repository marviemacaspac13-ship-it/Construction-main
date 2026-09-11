"""User-tunable estimating parameters.

Distinct from constants.py: these are knobs an estimator is expected to
change per project (wall height, waste allowance, bar spacing). Constants
are domain facts they should not.
"""

from pydantic import BaseModel, Field

from app.takeoff.constants import (
    COLUMN_SECTION_M,
    COLUMN_STANDARD_HEIGHT_M,
    COLUMN_TIES_PER_COLUMN,
    FOOTING_BARS_EACH_WAY,
    FOOTING_SIDE_M,
    RULES_VERSION,
    SLAB_MESH_M_PER_M2,
)


class EstimatingParams(BaseModel):
    # Geometry fallbacks
    default_wall_height_m: float = Field(3.0, gt=0, le=10)

    # Waste allowances, as a fraction added on top of net quantity
    chb_waste: float = Field(0.05, ge=0, lt=1)
    mortar_waste: float = Field(0.05, ge=0, lt=1)
    concrete_waste: float = Field(0.05, ge=0, lt=1)
    rebar_waste: float = Field(0.05, ge=0, lt=1)
    wire_waste: float = Field(0.10, ge=0, lt=1)
    conduit_waste: float = Field(0.10, ge=0, lt=1)
    pipe_waste: float = Field(0.05, ge=0, lt=1)

    # CHB wall reinforcement layout
    vertical_bar_spacing_m: float = Field(0.60, gt=0)
    horizontal_bar_spacing_m: float = Field(0.60, gt=0)
    rebar_item_id: str = "DB01"
    tie_wire_kg_per_100kg_rebar: float = Field(1.5, ge=0)

    # Electrical roughing-in
    slack_per_termination_m: float = Field(0.30, ge=0)

    # Openings, used when a plan's door/window schedule tags cannot be read.
    # Those tags sit inside small circles and OCR recovers almost none of
    # them (1 of 15 on the sample scan, and neither upscaling nor circle
    # cropping moved that much). Deducting nothing over-estimates masonry by
    # ~10%; assuming one of each per room lands within 1% on the one plan
    # whose true counts are known.
    doors_per_room: float = Field(1.0, ge=0)
    windows_per_room: float = Field(1.0, ge=0)

    # Structural frame, from Guide.docx. The sections, bar sizes and tie
    # count are the project standard rather than an assumption now; what
    # stays assumed is only where the frame SITS - how many columns, how
    # they are spaced, and the footing thickness, none of which the guide
    # states.
    include_frame: bool = True
    column_spacing_m: float = Field(3.5, gt=0, le=12)
    # GUIDE SILENT: footing plan size comes from the bar cut length, but its
    # thickness is never given. Still an assumption.
    footing_thickness_m: float = Field(0.20, gt=0, le=2)
    slab_thickness_m: float = Field(0.10, ge=0, le=1)
    # A perimeter tie beam. The guide specifies beams in full but says
    # nothing about where they run, so running one round the envelope is
    # the assumption.
    include_perimeter_beam: bool = True

    def assumption_lines(self) -> list[str]:
        """Human-readable assumptions, surfaced on every estimate."""
        lines = [
            f"Wall height defaults to {self.default_wall_height_m} m where not specified.",
            f"Vertical bars at {self.vertical_bar_spacing_m} m o.c., "
            f"horizontal at {self.horizontal_bar_spacing_m} m o.c. ({self.rebar_item_id}).",
            f"Waste allowance: CHB {self.chb_waste:.0%}, mortar {self.mortar_waste:.0%}, "
            f"rebar {self.rebar_waste:.0%}, wire {self.wire_waste:.0%}, pipe {self.pipe_waste:.0%}.",
            f"{self.slack_per_termination_m} m of conductor slack allowed per termination.",
            f"Where opening tags cannot be read, {self.doors_per_room:g} door and "
            f"{self.windows_per_room:g} window are assumed per room.",
        ]
        if self.include_frame:
            w, d = COLUMN_SECTION_M
            lines.append(
                f"Frame sections and steel follow the project guide "
                f"(rules {RULES_VERSION}): {w:g} x {d:g} m columns "
                f"{COLUMN_STANDARD_HEIGHT_M:g} m tall with {COLUMN_TIES_PER_COLUMN} ties "
                f"each, {FOOTING_SIDE_M:g} m square footings with "
                f"{FOOTING_BARS_EACH_WAY} bars each way, and a "
                f"{SLAB_MESH_M_PER_M2:g} m/m^2 slab mesh."
            )
            lines.append(
                f"Where the frame SITS is still assumed: columns at "
                f"{self.column_spacing_m:g} m o.c. round the envelope, "
                f"{self.footing_thickness_m:g} m footing thickness, a "
                f"{self.slab_thickness_m:g} m slab on grade"
                + (", and a perimeter tie beam." if self.include_perimeter_beam else ".")
            )
            lines.append(
                "Lap splices are not counted separately; the rebar waste allowance is "
                "the only slack."
            )
        return lines
