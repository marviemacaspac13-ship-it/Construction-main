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

    def assumption_lines(self) -> list[str]:
        """Human-readable assumptions, surfaced on every estimate."""
        return [
            f"Wall height defaults to {self.default_wall_height_m} m where not specified.",
            f"Vertical bars at {self.vertical_bar_spacing_m} m o.c., "
            f"horizontal at {self.horizontal_bar_spacing_m} m o.c. ({self.rebar_item_id}).",
            f"Waste allowance: CHB {self.chb_waste:.0%}, mortar {self.mortar_waste:.0%}, "
            f"rebar {self.rebar_waste:.0%}, wire {self.wire_waste:.0%}, pipe {self.pipe_waste:.0%}.",
            f"{self.slack_per_termination_m} m of conductor slack allowed per termination.",
        ]
