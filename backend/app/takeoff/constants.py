"""Philippine construction takeoff constants.

These are standard published figures, not measured facts. A quantity
surveyor should sign them off. Every estimate response reports which of
these it used, and RULES_VERSION stamps the set, so correcting a number
means bumping the version rather than silently shifting past estimates.
"""

# Bump on ANY change to a number in this file or to a rule formula.
RULES_VERSION = "2026.09.11"

# --- masonry -------------------------------------------------------------
# 0.40 m x 0.20 m block face = 0.08 m^2 -> 12.5 pcs per m^2 of wall.
CHB_PER_M2 = 12.5

CHB_ITEM: dict[str, str] = {"4in": "CHB01", "6in": "CHB02"}

# Mortar for LAYING blocks only (Class B 1:3), per m^2 of wall face.
# Plastering is a separate rule and is not included here.
CHB_MORTAR_PER_M2: dict[str, dict[str, float]] = {
    "4in": {"cement_bags": 0.35, "sand_m3": 0.0175},
    "6in": {"cement_bags": 0.44, "sand_m3": 0.0220},
}

# --- concrete ------------------------------------------------------------
# Per m^3 of poured concrete, by mix class.
CONCRETE_MIX_PER_M3: dict[str, dict[str, float]] = {
    "A": {"cement_bags": 9.0, "sand_m3": 0.50, "gravel_m3": 1.00},   # 1:2:4
    "B": {"cement_bags": 7.5, "sand_m3": 0.50, "gravel_m3": 1.00},   # 1:2.5:5
    "C": {"cement_bags": 6.0, "sand_m3": 0.50, "gravel_m3": 1.00},   # 1:3:6
}

# Mix class by element. Footings and columns carry load and get Class A;
# a slab on grade does not, and Class B is normal practice for it.
FRAME_MIX_CLASS = "A"
SLAB_MIX_CLASS = "B"

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

# --- standard opening sizes (PH residential) -----------------------------
# Used when a plan shows door/window TAGS but no schedule table.
DEFAULT_DOOR_M = (0.90, 2.10)
DEFAULT_WINDOW_M = (1.20, 1.20)
