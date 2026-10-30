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
    #
    # FROM Guide.docx: its standard wall is 5.00 x 2.70 m of 6-inch CHB,
    # pinned in tests/takeoff/test_guide_bills.py. This was 3.0 until Sep
    # 2026 with no source at all - the same height the guide's columns
    # contradict (2.7432 m) - and it inflated every floor-plan estimate by
    # about 2.6%, which is as much as measuring the true building outline
    # was ever going to recover. Floor plans do not state wall height, so
    # the project standard is the right fallback, not a round number.
    default_wall_height_m: float = Field(2.7, gt=0, le=10)

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
    # count are the project standard; footing and slab thickness are sourced
    # standards too (below). What stays genuinely assumed is only the LAYOUT
    # - how many columns and how they are spaced, and whether a perimeter
    # tie beam runs round the envelope - none of which any source states.
    include_frame: bool = True
    # Checked against the drawings on 25 Sep 2026. The two CAD plans draw
    # their columns as solid squares: 01.png has 16, 03.png has 10, 26 in
    # all. 3.5 m round each envelope gives 15 + 13 = 28 - two over, i.e.
    # slightly generous. The 6-8 m bay a commercial grid uses (Salvan) would
    # give 17, a third too few, so it does not carry to a bungalow. 3.6 m
    # would match these two exactly, but two sheets are not grounds to tune
    # it; counting the drawn columns is the real fix where they are drawn.
    column_spacing_m: float = Field(3.5, gt=0, le=12)
    # FROM THE NSCP 2015 (following ACI 318), confirmed by the owner on
    # 25 Sep 2026: a spread footing needs at least 150 mm of concrete ABOVE
    # its bottom reinforcement - a depth over the bars, not an overall
    # thickness. Overall is therefore that 150 mm plus the bars plus the
    # cover beneath them:
    #
    #     75 mm cover (CONCRETE_COVER_M["footing"], cast against earth)
    #   + 32 mm       (the guide's 16 mm mat, one layer each way)
    #   + 150 mm      (NSCP minimum above the bars)
    #   = 257 mm, drafted as 250 mm
    #
    # It was 0.20 until then, from reading the NSCP figure as a total; that
    # left only ~93 mm above the bars and understated every footing by 20%.
    # Guide.docx gives footing plan size (from the bar cut length) but
    # never its thickness.
    footing_thickness_m: float = Field(0.25, gt=0, le=2)
    # FROM Guide.docx: its standard slab is 5 x 5 m at 100 mm (the bill in
    # tests/takeoff/test_guide_bills.py). The most sensitive value in a
    # floor-plan estimate - each 25 mm moves the total about 6% - and not
    # on any floor plan, so the project standard is what stands in for it.
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
    #
    # Since 25 Sep 2026 this and the conduit figure below apply to
    # CONVENIENCE OUTLETS only. Lighting has its own allowance, further down.
    wire_m_per_device: float = Field(20.0, ge=0, le=100)

    # CONDUIT holds at 6.0, and the derivation is worth keeping because it
    # explains the 20 above. NBCP Rule VIII sets a 2.70 m ceiling for a
    # single-storey dwelling and trade practice sets an outlet 0.30 m above
    # finished floor, so the drop is 2.40 m and the horizontal run to the
    # ceiling junction box is ~3.60 m. That is 6.0 m - exactly two of the
    # 3.0 m sticks PVC conduit is sold in here (Neltex, Emerald, Atlanta),
    # which is what estimators actually budget.
    conduit_m_per_device: float = Field(6.0, ge=0, le=100)

    # LIGHTING POINTS are not outlets, and pricing them at the outlet's 20 m
    # over-counted the largest line in the trade (owner, 25 Sep 2026). A
    # light sits in the ceiling plane: the run loops fixture to fixture
    # along the ceiling and drops down a wall only for the switch leg, so
    # there is no 2.40 m wall drop per point.
    #
    # THIS IS AN ESTIMATING ASSUMPTION, NOT A PHILIPPINE-STANDARD VALUE. The
    # PEC prescribes no "metres of wire per lighting point". What it does
    # govern is grounding and bonding where applicable, and the number of
    # conductors follows from the wiring method, which a plan does not show.
    # So the figure is built from its parts and each part is a knob:
    #
    #     route per point   3.6 m   the ceiling run between fixtures - the
    #                               same horizontal run the outlet conduit
    #                               above is built from, without its drop
    #     conductors        3       line, neutral and an equipment ground;
    #                               2 where the wiring method carries none
    #     free conductor    0.15 m  at each of the two boxes (PEC 3.00.14)
    #
    #     3 x (3.6 + 2 x 0.15) = 11.7 m of wire and 3.6 m of conduit
    #
    # 3 conductors is chosen as the cautious side: short wire stops a job,
    # spare wire does not. At 2 it is 7.8 m.
    lighting_route_m_per_point: float = Field(3.6, ge=0, le=100)
    lighting_conductors: int = Field(3, ge=1, le=6)
    box_free_conductor_m: float = Field(0.15, ge=0, le=1)

    @property
    def lighting_wire_m_per_point(self) -> float:
        # No run means no wire: the box allowance alone must not keep a
        # switched-off line alive at 0.9 m a point.
        if self.lighting_route_m_per_point <= 0:
            return 0.0
        return self.lighting_conductors * (
            self.lighting_route_m_per_point + 2 * self.box_free_conductor_m
        )

    # The plumbing allowances also held: a Philippine bathroom is compact
    # (~1.5 x 2.0 m) with the main line just outside the wall or overhead,
    # so a fixture branch stays inside one 3.0 m length. Published practice
    # is 2.0-2.5 m supply and 1.5-2.5 m drain per fixture; the 2.0 m
    # defaults below sit inside both.
    main_run_m_per_fixture: float = Field(1.5, ge=0, le=50)

    def tagged_assumptions(
        self, columns_counted: int | None = None, manual_column_count: int | None = None
    ) -> list[tuple[str, str]]:
        """Every assumption, paired with the rule family it belongs to.

        Tagged rather than filtered by plan type, so a rule brings its own
        assumption and nothing has to be kept in sync by hand. The waste
        allowances are split the same way: an electrical estimate has no
        business declaring a mortar allowance.

        `columns_counted` is how many columns were counted on the drawing,
        if they were. Then the spacing is not an assumption this estimate
        rests on, and saying it was would misdescribe it.
        """
        lines: list[tuple[str, str]] = [
            (
                "structural",
                f"Wall height defaults to {self.default_wall_height_m:g} m where not specified - "
                f"the Guide.docx standard wall (5.00 x 2.70 m); floor plans do not state it.",
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
                f"{self.conduit_m_per_device:g} m of conduit per convenience outlet. No plan "
                f"states these lengths, so they are not measurements of THIS building - but "
                f"they are not invented either: they follow Philippine practice (Fajardo; PEC "
                f"Part 1 2017 Art. 2.50 and 3.00.14; NBCP Rule VIII), where a 6 m conduit run "
                f"carries three conductors and the boxes take 150 mm of free wire each. Wire "
                f"remains the largest single cost in the trade.",
            ),
            (
                "electrical",
                f"Lighting points are allowed {self.lighting_wire_m_per_point:g} m of wire and "
                f"{self.lighting_route_m_per_point:g} m of conduit each: a "
                f"{self.lighting_route_m_per_point:g} m ceiling run between fixtures, "
                f"{self.lighting_conductors} conductors, and "
                f"{self.box_free_conductor_m * 1000:g} mm of free wire at each box. This is an "
                f"estimating assumption, not a Philippine-standard value - the PEC sets no "
                f"length per lighting point, and the conductor count depends on a wiring "
                f"method the plan does not show.",
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
            (
                "plumbing",
                "Kitchen sinks, showers, bathtubs, washing machines and drinking fountains each "
                "take a 2-inch drain with a wye and a 1/2-inch supply with a tee; a hose bib takes "
                "supply only. These pairings are an estimating assumption chosen by the owner on "
                "30 Oct 2026, not values from a plumbing standard.",
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
                    (
                        (
                            f"Columns manually confirmed: {manual_column_count}, interior "
                            if manual_column_count is not None else
                            f"Columns were counted on the drawing: {columns_counted}, interior "
                        )
                        + f"ones included, each on its own footing. Only the tie beam is "
                        f"still assumed"
                        + (" - one round the perimeter." if self.include_perimeter_beam else ".")
                    )
                    if columns_counted or manual_column_count is not None
                    else (
                        f"Where the frame SITS is still assumed: columns at "
                        f"{self.column_spacing_m:g} m o.c. round the envelope"
                        + (", and a perimeter tie beam." if self.include_perimeter_beam else ".")
                    ),
                ),
                (
                    "structural",
                    f"Footing and slab thickness are standards, not readings - a floor plan "
                    f"shows neither: {self.footing_thickness_m:g} m footings per the NSCP (150 mm "
                    f"above the bars, plus the bars and 75 mm cover), and a {self.slab_thickness_m:g} m slab on grade per the "
                    f"Guide.docx standard slab (5 x 5 m at 100 mm).",
                ),
                (
                    "structural",
                    "Lap splices are not counted separately; the rebar waste allowance is "
                    "the only slack.",
                ),
            ]
        return lines

    def assumption_lines(
        self,
        families: Collection[str] | None = None,
        columns_counted: int | None = None,
        manual_column_count: int | None = None,
    ) -> list[str]:
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
            for family, text in self.tagged_assumptions(columns_counted, manual_column_count)
            if families is None or family in families
        ]
