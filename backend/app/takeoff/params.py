"""User-tunable estimating parameters.

Distinct from constants.py: these are knobs an estimator is expected to
change per project (wall height, waste allowance, bar spacing). Constants
are domain facts they should not.
"""

from pydantic import BaseModel, Field


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

    # Structural frame. No residential floor plan prints its column schedule,
    # and the sections cannot be read off the drawing the way dimensions can,
    # so every number below is an assumption rather than a measurement. It
    # matters more than most: volume scales with the SQUARE of the column
    # section, so 0.30 x 0.30 is 2.25x the concrete of 0.20 x 0.20. The
    # defaults are the common Philippine single-storey residential sections.
    include_frame: bool = True
    column_width_m: float = Field(0.20, gt=0, le=2)
    column_depth_m: float = Field(0.20, gt=0, le=2)
    column_spacing_m: float = Field(3.5, gt=0, le=12)
    footing_width_m: float = Field(0.80, gt=0, le=5)
    footing_length_m: float = Field(0.80, gt=0, le=5)
    footing_thickness_m: float = Field(0.20, gt=0, le=2)
    slab_thickness_m: float = Field(0.10, ge=0, le=1)

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
            lines.append(
                f"Structural frame assumed, not read: {self.column_width_m:g} x "
                f"{self.column_depth_m:g} m columns at {self.column_spacing_m:g} m o.c. "
                f"on {self.footing_width_m:g} x {self.footing_length_m:g} x "
                f"{self.footing_thickness_m:g} m footings, with a "
                f"{self.slab_thickness_m:g} m slab on grade."
            )
        return lines
