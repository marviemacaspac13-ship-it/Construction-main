"""Philippine construction takeoff constants.

**These now come from Guide.docx**, the project standard, rather than from
generic published tables. Where the guide states a figure it wins; where it
is silent the previous assumption stands and says so below.

The guide gives a bill of materials per standard member - a 2.7 m column, a
5 m beam, 25 m2 of slab, a 5 x 2.7 m wall - and highlights those totals as
the base of the calculation. Every rate here is set so that multiplying it
back out reproduces those highlighted totals exactly. `tests/takeoff/
test_guide_bills.py` pins that, and is the real specification.

RULES_VERSION stamps the set, so correcting a number means bumping the
version rather than silently shifting past estimates.
"""

# Bump on ANY change to a number in this file or to a rule formula.
RULES_VERSION = "2026.09.12"

# --- masonry -------------------------------------------------------------
# 0.40 m x 0.20 m block face = 0.08 m^2 -> 12.5 pcs per m^2 of wall.
CHB_PER_M2 = 12.5

CHB_ITEM: dict[str, str] = {"4in": "CHB01", "6in": "CHB02"}

# Mortar for LAYING blocks only (1:3), per m^2 of wall face, BEFORE waste.
# Plastering is a separate rule and is not included here.
#
# The guide gives 2.86 bags and 0.11 m3 for a 5.00 x 2.70 m wall - 13.5 m2 -
# and its block figure on the same line carries 5% waste, so these are read
# as post-waste totals and divided back out: 2.86 / 1.05 / 13.5 = 0.201764.
#
# GUIDE SILENT: it does not separate 4in from 6in. The 4in rate keeps the
# ratio the previous table used (0.35 : 0.44) applied to the guide 6in
# figure, rather than charging a 4in wall for 6in of bedding.
CHB_MORTAR_PER_M2: dict[str, dict[str, float]] = {
    "4in": {"cement_bags": 0.160494, "sand_m3": 0.0061729},
    "6in": {"cement_bags": 0.201764, "sand_m3": 0.0077601},
}

# --- concrete ------------------------------------------------------------
# Per m^3 of poured concrete, by mix class, via the dry-factor method the
# guide works through: 1 m3 wet x 1.54 dry factor, split by mix parts, and
# cement at 1440 kg/m3 in 40 kg bags.
#
#   Class A 1:2:4 -> 1.54/7 x 1440 / 40 = 7.92 bags, 1.54x2/7 sand, 1.54x4/7 gravel
#
# The guide only works Class A. B and C are extended by the same method so
# the three classes stay consistent with each other.
CONCRETE_MIX_PER_M3: dict[str, dict[str, float]] = {
    "A": {"cement_bags": 7.92, "sand_m3": 0.4400, "gravel_m3": 0.8800},  # 1:2:4
    "B": {"cement_bags": 6.52, "sand_m3": 0.4529, "gravel_m3": 0.9059},  # 1:2.5:5
    "C": {"cement_bags": 5.54, "sand_m3": 0.4620, "gravel_m3": 0.9240},  # 1:3:6
}

# The guide pours the slab at 1:2:4 like everything else, so the slab is no
# longer dropped to Class B.
FRAME_MIX_CLASS = "A"
SLAB_MIX_CLASS = "A"

# Clear concrete cover, metres. A code requirement rather than a
# preference: footings are cast against earth and need the most, a slab on
# grade the least. Sets how much shorter than its member each bar runs.
CONCRETE_COVER_M: dict[str, float] = {
    "footing": 0.075,
    "column": 0.040,
    "beam": 0.040,
    "slab": 0.020,
}

# --- the guide standard members -----------------------------------------
# Section shared by columns and beams: 200 mm wide x 400 mm deep, 40 mm
# cover. Both therefore take the same 0.88 m tie loop:
#   2 x ((200 - 2x40) + (400 - 2x40)) = 2 x (120 + 320) = 880 mm
COLUMN_SECTION_M = (0.20, 0.40)
BEAM_SECTION_M = (0.20, 0.40)

# AMBIGUITY: the guide says "fix to 2.7m (standard)" but every calculation
# uses 2.7432 m, which is 9 feet. The highlighted per-column bill derives
# from 2.7432, and the highlighted totals are stated to be the base of the
# calculation, so 2.7432 wins and 2.7 is read as the nominal label.
COLUMN_STANDARD_HEIGHT_M = 2.7432

# AMBIGUITY: 24 ties per standard column is stated as a count with no
# spacing rule behind it, so it is carried as a count. Over 2.7432 m that
# implies roughly 119 mm centres, tighter than a plain spacing rule would
# give, which is normal where the ends are confined.
COLUMN_TIES_PER_COLUMN = 24

# Footing: the bar cut length of 1.15 - 2(0.075) fixes a 1.15 m square at
# 75 mm cover, with 6 bars each way.
FOOTING_SIDE_M = 1.15
FOOTING_BARS_EACH_WAY = 6

# Beam stirrup zones, from the worked 5 m example: 0.50 m at 50 mm centres,
# 0.50 m at 100 mm, 1.00 m at 150 mm, and whatever is left at 200 mm. Each
# zone counts its spacings plus one.
# AMBIGUITY: the guide lays the zones down once over the beam rather than
# once per end, which is unusual for confinement but is what it computes,
# and 11 + 6 + 8 + 16 = 41 only reproduces if they are counted once.
BEAM_STIRRUP_ZONES: tuple[tuple[float, float], ...] = ((0.50, 0.05), (0.50, 0.10), (1.00, 0.15))
BEAM_STIRRUP_REST_SPACING_M = 0.20
BEAM_MAIN_BARS = 4  # 2 top + 2 bottom

# Slab reinforcement as a rate rather than a spacing.
# AMBIGUITY: the guide states 200 mm spacing both ways but its own worked
# example gives 210 m over 25 m2, which is 8.4 m/m2 post-waste and matches
# 250 mm, not 200. The highlighted total governs, so the rate is used.
SLAB_MESH_M_PER_M2 = 8.0

# Bar sizes the guide calls for.
MAIN_BAR_ITEM = "DB03"  # 16mm - column verticals, beam mains, footing mats
TIE_BAR_ITEM = "DB01"   # 10mm - column ties, beam stirrups, slab mesh

CEMENT_ITEM = "CMT01"
SAND_ITEM = "SND02"
GRAVEL_ITEM = "GVF01"
TIE_WIRE_ITEM = "GI01"

# --- reinforcement -------------------------------------------------------
# Nominal unit mass of deformed bar, kg per linear metre.
REBAR_KG_PER_M: dict[str, float] = {"DB01": 0.617, "DB02": 0.888, "DB03": 1.578}

# --- electrical ----------------------------------------------------------
# Conductor gauge selected by circuit service type.
WIRE_ITEM_BY_SERVICE: dict[str, str] = {
    "lighting": "ELW05",          # #14 AWG
    "convenience": "ELW04",       # #12 AWG
    "aircon": "ELW03",            # #10 AWG
    "service_entrance": "ELW01",  # #6 AWG
}

CONDUIT_ITEM = "FPVC01"
UTILITY_BOX_ITEM = "UTB01"
JUNCTION_BOX_ITEM = "JCB01"

# Devices that get a utility box roughed in behind them.
WIRING_DEVICE_ITEMS: frozenset[str] = frozenset(
    {"GS01", "GS02", "GS03", "SW01", "SW02", "SW03", "OT01", "OT02", "OT03", "ACO01"}
)

# Ceiling outlets that get a junction box.
CEILING_OUTLET_ITEMS: frozenset[str] = frozenset({"CLR01", "CLR02", "CLR03"})

# --- plumbing ------------------------------------------------------------
SUPPLY_PIPE_ITEM: dict[str, str] = {'1/2"': "PCSP01", '3/4"': "PCSP02"}
DRAIN_PIPE_ITEM: dict[str, str] = {'2"': "PDP01", '3"': "PDP02", '4"': "PDP03"}

# --- sanitary fixtures ---------------------------------------------------
# What each fixture on a plumbing plan pulls with it. The fixture itself is
# never priced - it is client-supplied, the same way a floor plan prices
# walls but not the doors in them - so a tag is only worth counting because
# of the pipe and fittings it implies.
#
# Drains branch with a WYE rather than a tee: the shallow 45 degree angle
# keeps solids moving where a square tee would trap them. Supply branches
# use a plain tee. Sizes are PH sanitary practice - 4" off a water closet,
# 2" off everything else.
FIXTURE_PLUMBING: dict[str, dict[str, str]] = {
    "water_closet": {
        "drain": "PDP03", "drain_fitting": "PVYO03",
        "supply": "PCSP01", "supply_fitting": "PVTB01",
    },
    "lavatory": {
        "drain": "PDP01", "drain_fitting": "PVYO01",
        "supply": "PCSP01", "supply_fitting": "PVTB01",
    },
    "urinal": {
        "drain": "PDP01", "drain_fitting": "PVYO01",
        "supply": "PCSP01", "supply_fitting": "PVTB01",
    },
    # A floor drain takes waste away and is fed by nothing.
    "floor_drain": {"drain": "PDP01", "drain_fitting": "PVYO01"},
    # A cleanout is an access point on a line that already exists. It adds
    # no pipe of its own and has no catalog row, so it is counted and
    # nothing more.
    "cleanout": {},
}

# Tags as they are printed beside the fixture, for app/extract/tags.py.
FIXTURE_TAG_PATTERNS: dict[str, str] = {
    "water_closet": r"WC",
    "lavatory": r"LAV",
    "urinal": r"U",
    "floor_drain": r"FD",
    "cleanout": r"C\.?O\.?",
}

# --- standard opening sizes (PH residential) -----------------------------
# Used when a plan shows door/window TAGS but no schedule table.
DEFAULT_DOOR_M = (0.90, 2.10)
DEFAULT_WINDOW_M = (1.20, 1.20)
