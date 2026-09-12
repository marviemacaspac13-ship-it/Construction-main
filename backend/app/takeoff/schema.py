"""The single hand-off record between extraction and computation.

Populated by OCR extraction, by CV geometry extraction, by a DXF parser,
or by a human filling in a form. Nothing downstream may ask where it came
from.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

PlanType = Literal["Floor Plan", "Electrical Plan", "Plumbing Plan"]
WallThickness = Literal["4in", "6in"]
MixClass = Literal["A", "B", "C"]
Service = Literal[
    "lighting", "convenience", "aircon", "service_entrance", "supply", "drain"
]
PLUMBING_SERVICES: frozenset[str] = frozenset({"supply", "drain"})

ScaleSource = Literal[
    "manual",
    "printed_dimension",
    "scale_bar",
    "known_reference",
    "stated_ratio",
]


class Scale(BaseModel):
    meters_per_pixel: float = Field(gt=0)
    confirmed_by_user: bool = False
    source: ScaleSource = "manual"
    confidence: float = Field(1.0, ge=0, le=1)


class Opening(BaseModel):
    kind: Literal["door", "window"]
    width_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    count: int = Field(1, ge=1)

    @property
    def area_m2(self) -> float:
        return self.width_m * self.height_m * self.count


class Wall(BaseModel):
    id: str
    length_m: float = Field(gt=0)
    thickness: WallThickness = "6in"
    height_m: Optional[float] = Field(None, gt=0)
    openings: list[Opening] = Field(default_factory=list)

    @property
    def gross_area_m2(self) -> float:
        return self.length_m * (self.height_m or 0.0)

    @property
    def opening_area_m2(self) -> float:
        return sum(o.area_m2 for o in self.openings)

    def effective_height_m(self, default_height_m: float) -> float:
        return self.height_m if self.height_m is not None else default_height_m

    def net_area_m2(self, default_height_m: float) -> float:
        gross = self.length_m * self.effective_height_m(default_height_m)
        return max(0.0, gross - self.opening_area_m2)


class Room(BaseModel):
    id: str
    name: str = ""
    area_m2: float = Field(gt=0)
    width_m: Optional[float] = Field(None, gt=0)
    length_m: Optional[float] = Field(None, gt=0)


class ConcreteElement(BaseModel):
    """A pour, optionally described well enough to reinforce.

    Volume alone cannot be reinforced: steel depends on how many members
    there are and what shape each one is, not on how much concrete they
    add up to. An element that carries member geometry gets rebar; one
    that carries only a volume is priced as concrete and left unreinforced.
    """

    id: str
    kind: Literal["footing", "column", "beam", "slab"]
    volume_m3: float = Field(gt=0)
    mix_class: MixClass = "A"

    # Identical members this line stands for, and the size of one of them.
    count: int = Field(1, ge=1)
    width_m: Optional[float] = Field(None, gt=0)
    length_m: Optional[float] = Field(None, gt=0)
    height_m: Optional[float] = Field(None, gt=0)

    @property
    def is_reinforceable(self) -> bool:
        return None not in (self.width_m, self.length_m, self.height_m)


class Run(BaseModel):
    """A linear route - an electrical circuit or a pipe run."""

    id: str
    length_m: float = Field(gt=0)
    service: Service
    diameter: Optional[str] = None  # plumbing only
    conductors: int = Field(2, ge=1)  # electrical only
    terminations: int = Field(0, ge=0)  # boxes on this run, for slack

    @model_validator(mode="after")
    def _plumbing_needs_diameter(self) -> "Run":
        if self.service in PLUMBING_SERVICES and not self.diameter:
            raise ValueError(f"run {self.id}: {self.service} run requires a diameter")
        return self


class FixtureCount(BaseModel):
    item_id: str
    count: int = Field(ge=0)


class PlanSchema(BaseModel):
    plan_type: PlanType
    scale: Optional[Scale] = None
    walls: list[Wall] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    concrete: list[ConcreteElement] = Field(default_factory=list)
    runs: list[Run] = Field(default_factory=list)
    fixtures: list[FixtureCount] = Field(default_factory=list)

    # Things counted on the drawing that are NOT themselves bought: the
    # toilets and lavatories on a sanitary plan, which the client supplies.
    # They earn their place by driving what IS bought - the pipe and
    # fittings that serve them - exactly as a detected outlet drives the
    # utility box behind it. Keyed by tag name, not by item_id, because
    # they have no catalog row and never will.
    fixture_tags: dict[str, int] = Field(default_factory=dict)

    source: Literal["manual", "detection", "ocr", "tags", "cad"] = "manual"
