"""The four real sample plans, transcribed by hand from the drawings.

These stand in for OCR output: they are exactly what a reader should
produce from each image. Every number here was read off the drawing, so a
test that passes against these is testing the takeoff logic, not the OCR.
"""

from dataclasses import dataclass, field


@dataclass
class SamplePlan:
    key: str
    description: str
    envelope_w: float
    envelope_l: float
    expected_unit: str
    room_blocks: list[str]
    chains: list[tuple[list[float], float]]
    opening_tags: list[str] = field(default_factory=list)


NOTEBOOK = SamplePlan(
    key="notebook",
    description="Hand-drawn plan on ruled paper, centimetres",
    envelope_w=830,
    envelope_l=1350,
    expected_unit="cm",
    room_blocks=[
        "KITCHEN 390x420",
        "BED 390x400",
        "DINING 420x370",
        "TOILET 370x130",
        "LIVING 370x480",
        "SIT-OUT 390x300",
        "BED 390x360",
    ],
    chains=[
        ([70, 390, 370], 830),
        ([70, 370, 390], 830),
        ([420, 370, 480, 80], 1350),
        ([180, 1170], 1350),
    ],
)

CAD_WIDE = SamplePlan(
    key="cad_wide",
    description="CAD render, 4 bedrooms, millimetres",
    envelope_w=14000,
    envelope_l=11000,
    expected_unit="mm",
    room_blocks=[
        "BEDROOM 2 3200 x 4000",
        "KITCHEN 3700 x 4000",
        "BEDROOM 3 3300 x 4000",
        "BEDROOM 4 3800 x 4000",
        "TOILET 2200 x 1500",
        "BATHROOM 2 3000 x 1500",
        "BATHROOM 1 3000 x 1700",
        "BEDROOM 2 3200 x 3800",
        "LIVING ROOM 5400 x 3800",
        "BEDROOM 1 3800 x 4000",
    ],
    chains=[
        ([3200, 3700, 3300, 3800], 14000),
        ([3200, 5400, 2400, 3000], 14000),
        ([4000, 1500, 1700, 3800], 11000),
        ([4000, 3000, 4000], 11000),
    ],
)

CAD_SQUARE = SamplePlan(
    key="cad_square",
    description="CAD render, 2 bedrooms, millimetres",
    envelope_w=11500,
    envelope_l=10000,
    expected_unit="mm",
    room_blocks=[
        "KITCHEN 4200 x 3500",
        "BEDROOM 2 3700 x 3500",
        "BATHROOM 2 2500 x 1600",
        "BATHROOM 1 2500 x 1600",
        "LIVING ROOM 6000 x 6500",
        "BEDROOM 1 3700 x 3300",
    ],
    chains=[
        ([1800, 4200, 1800, 3700], 11500),
        ([1800, 6000, 3700], 11500),
        ([3500, 6500], 10000),
        ([3500, 1600, 1600, 3300], 10000),
    ],
)

# The hard case: decimals, a cumulative running total (954) mixed into the
# left chain, a coarse chain that rounds to 1025 against a stated 1026, and
# door/window schedule tags instead of drawn arcs.
KERALA = SamplePlan(
    key="kerala",
    description="Scanned architectural plan, centimetres, tagged openings",
    envelope_w=1026,
    envelope_l=1049,
    expected_unit="cm",
    room_blocks=[
        "BED ROOM 294X294",
        "DINING 312X444",
        "KITCHEN 324X240",
        "W/C 192X138",
        "STORE 120X180",
        "BED ROOM 294X438",
        "HALL 528X372",
        "SIT-OUT 312X138",
    ],
    chains=[
        ([96, 150, 177, 150, 105, 90, 42, 150, 66], 1026),
        ([96, 150, 140, 50, 200, 150, 168, 954, 95], 1049),
        ([318, 360, 215, 132], 1026),
    ],
    opening_tags=[
        "W3", "W3", "W3", "W3", "W3", "W3", "W3", "W3", "W2",
        "D1", "D1", "D1", "D2", "D2", "D",
        "V", "V",
    ],
)

ALL_PLANS = [NOTEBOOK, CAD_WIDE, CAD_SQUARE, KERALA]