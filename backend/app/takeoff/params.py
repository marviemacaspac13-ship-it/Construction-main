"""User-tunable estimating parameters.

Distinct from constants.py: these are knobs an estimator is expected to
change per project (wall height, waste allowance, bar spacing). Constants
are domain facts they should not.
"""

from collections.abc import Collection

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

    # Sanitary branch runs. Nothing on a plumbing plan states how far a
    # fixture sits from the line it joins, and tracing the pipe routes is a
    # separate job entirely, so each fixture is allowed a branch length.
    # These are the least-supported numbers in the engine: Guide.docx covers
    # concrete and masonry only, and there is no plumbing equivalent.
    drain_branch_m_per_fixture: float = Field(2.0, ge=0, le=20)
    supply_branch_m_per_fixture: float = Field(2.0, ge=0, le=20)

    # Length from counts. Wire, conduit and pipe are sold by the metre and
    # are the majority of electrical and plumbing cost, but no drawing states
    # those lengths and nothing here measures them. These allowances turn the
    # counts we CAN read into the lengths we cannot.
    #
    # Configured once per project, never asked at scan time - the same shape
    # as the wall height and waste allowances above.
    #
    # These began as my own guesses, and were checked in Sep 2026 against
    # Philippine estimating practice - Fajardo, "Electrical Layout and
    # Estimate" and "Simplified Construction Estimate"; PEC Part 1 (2017);
    # NBCP (P.D. 1096). Three of the four survived. One did not.
    #
    # WIRE was 12.0 and is badly wrong at that. 12 m assumes a two-wire
    # circuit, but PEC Art. 2.50 mandates an equipment grounding conductor
    # on every branch circuit feeding a grounding-type receptacle, so three
    # conductors share the conduit, not two:
    #
    #     6.0 m conduit x 3 conductors            = 18.0 m
    #     Art. 3.00.14 free conductor, 150 mm     ~  1.5 m over the boxes
    #                                               ------
    #                                               ~20.0 m
    #
    # At 12 m an electrical estimate came out ~40% short on its largest
    # line. This is the second constant an outside source has corrected by
    # a wide margin, after Guide.docx doubled the column section.
    wire_m_per_device: float = Field(20.0, ge=0, le=100)

    # CONDUIT holds at 6.0, and the derivation is worth keeping because it
    # explains the 20 above. NBCP Rule VIII sets a 2.70 m ceiling for a
    # single-storey dwelling and trade practice sets an outlet 0.30 m above
    # finished floor, so the drop is 2.40 m and the horizontal run to the
    # ceiling junction box is ~3.60 m. That is 6.0 m - exactly two of the
    # 3.0 m sticks PVC conduit is sold in here (Neltex, Emerald, Atlanta),
    # which is what estimators actually budget.
    conduit_m_per_device: float = Field(6.0, ge=0, le=100)

    # The plumbing allowances also held: a Philippine bathroom is compact
    # (~1.5 x 2.0 m) with the main line just outside the wall or overhead,
    # so a fixture branch stays inside one 3.0 m length. Published practice
    # is 2.0-2.5 m supply and 1.5-2.5 m drain per fixture; the 2.0 m
    # defaults below sit inside both.
    main_run_m_per_fixture: float = Field(1.5, ge=0, le=50)

    def tagged_assumptions(self) -> list[tuple[str, str]]:
        """Every assumption, paired with the rule family it belongs to.

        Tagged rather than filtered by plan type, so a rule brings its own
        assumption and nothing has to be kept in sync by hand. The waste
        allowances are split the same way: an electrical estimate has no
        business declaring a mortar allowance.
        """
        lines: list[tuple[str, str]] = [
            (
                "structural",
                f"Wall height defaults to {self.default_wall_height_m} m where not specified.",
            ),
            (
                "structural",
                f"Vertical bars at {self.vertical_bar_spacing_m} m o.c., "
                f"horizontal at {self.horizontal_bar_spacing_m} m o.c. ({self.rebar_item_id}).",
            ),
            (
                "structural",
                f"Waste allowance: CHB {self.chb_waste:.0%}, mortar {self.mortar_waste:.0%}, "
                f"concrete {self.concrete_waste:.0%}, rebar {self.rebar_waste:.0%}.",
            ),
            (
                "structural",
                f"Where opening tags cannot be read, {self.doors_per_room:g} door and "
                f"{self.windows_per_room:g} window are assumed per room.",
            ),
            (
                "electrical",
                f"Waste allowance: wire {self.wire_waste:.0%}, "
                f"conduit {self.conduit_waste:.0%}.",
            ),
            (
                "electrical",
                f"{self.slack_per_termination_m} m of conductor slack allowed per termination.",
            ),
            (
                "electrical",
                f"Where no circuit routes are measured, wire and conduit are derived from the "
                f"device count at {self.wire_m_per_device:g} m of conductor and "
                f"{self.conduit_m_per_device:g} m of conduit per device. No plan states these "
                f"lengths, so they are not measurements of THIS building - but they are not "
                f"invented either: they follow Philippine practice (Fajardo; PEC Part 1 2017 "
                f"Art. 2.50 and 3.00.14; NBCP Rule VIII), where a 6 m conduit run carries "
                f"three conductors and the boxes take 150 mm of free wire each. Wire remains "
                f"the largest single cost in the trade.",
            ),
            ("plumbing", f"Waste allowance: pipe {self.pipe_waste:.0%}."),
            (
                "plumbing",
                f"Fixtures are counted but not priced - they are client-supplied. "
                f"Each is allowed {self.drain_branch_m_per_fixture:g} m of drain and "
                f"{self.supply_branch_m_per_fixture:g} m of supply pipe to reach its "
                f"line. No plan states either, but both sit inside published "
                f"Philippine practice for a compact bathroom - 2.0-2.5 m supply "
                f"and 1.5-2.5 m drain per fixture (Fajardo, Plumbing Design and "
                f"Estimate).",
            ),
            (
                "plumbing",
                f"A further {self.main_run_m_per_fixture:g} m per fixture is allowed for the "
                f"shared run back to the main, which no plan dimensions either.",
            ),
        ]
        if self.include_frame:
            w, d = COLUMN_SECTION_M
            lines += [
                (
                    "structural",
                    f"Frame sections and steel follow the project guide "
                    f"(rules {RULES_VERSION}): {w:g} x {d:g} m columns "
                    f"{COLUMN_STANDARD_HEIGHT_M:g} m tall with {COLUMN_TIES_PER_COLUMN} ties "
                    f"each, {FOOTING_SIDE_M:g} m square footings with "
                    f"{FOOTING_BARS_EACH_WAY} bars each way, and a "
                    f"{SLAB_MESH_M_PER_M2:g} m/m^2 slab mesh.",
                ),
                (
                    "structural",
                    f"Where the frame SITS is still assumed: columns at "
                    f"{self.column_spacing_m:g} m o.c. round the envelope, "
                    f"{self.footing_thickness_m:g} m footing thickness, a "
                    f"{self.slab_thickness_m:g} m slab on grade"
                    + (", and a perimeter tie beam." if self.include_perimeter_beam else "."),
                ),
                (
                    "structural",
                    "Lap splices are not counted separately; the rebar waste allowance is "
                    "the only slack.",
                ),
            ]
        return lines

    def assumption_lines(self, families: Collection[str] | None = None) -> list[str]:
        """Assumptions that actually applied to an estimate.

        `families` is the set of rule families that fired - "structural",
        "electrical", "plumbing" - taken from the BOM. Passing None returns
        everything, which is what a caller with no BOM to hand should do.

        Nothing renders these; they go to the ledger in app/audit.py, which
        is the only record of what an estimate rests on. A ledger claiming
        an electrical job assumed a rebar spacing is worse than no ledger.
        """
        return [
            text
            for family, text in self.tagged_assumptions()
            if families is None or family in families
        ]
