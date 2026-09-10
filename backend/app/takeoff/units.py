"""Purchase-unit kinds per SKU.

The catalog's `unit` column is display text and is NOT machine-readable:
`PCSP01` is `1/2" / 3meter` while `PCSP02` is `3/4" / 3 meter`, and `PB01`
is null. Quantity math reads this table instead.

kind meanings:
  each       - sold per piece/set; quantity is a whole count
  linear_m   - sold by the metre; quantity is metres
  stick      - sold as a fixed-length piece; quantity is whole pieces,
               derived from required metres / stick_length_m
  bag        - sold per sack; quantity is whole bags
  volume_m3  - sold by cubic metre; quantity is m3
  mass_kg    - sold by kilogram; quantity is kg
"""

from typing import Literal

from pydantic import BaseModel

UnitKind = Literal["each", "linear_m", "stick", "bag", "volume_m3", "mass_kg"]


class UnitSpec(BaseModel, frozen=True):
    kind: UnitKind
    stick_length_m: float | None = None


_EACH = UnitSpec(kind="each")
_LINEAR = UnitSpec(kind="linear_m")
_STICK_3M = UnitSpec(kind="stick", stick_length_m=3.0)
_STICK_6M = UnitSpec(kind="stick", stick_length_m=6.0)

UNIT_SPECS: dict[str, UnitSpec] = {
    # ---- structural ----
    "CHB01": _EACH,
    "CHB02": _EACH,
    "CMT01": UnitSpec(kind="bag"),
    "GVF01": UnitSpec(kind="volume_m3"),
    "SND01": UnitSpec(kind="volume_m3"),
    "SND02": UnitSpec(kind="volume_m3"),
    # Deformed bars are priced "per pc"; PH commercial length is 6.0 m.
    "DB01": _STICK_6M,
    "DB02": _STICK_6M,
    "DB03": _STICK_6M,
    "GI01": UnitSpec(kind="mass_kg"),
    # ---- electrical ----
    "ELW01": _LINEAR,
    "ELW02": _LINEAR,
    "ELW03": _LINEAR,
    "ELW04": _LINEAR,
    "ELW05": _LINEAR,
    "FPVC01": _LINEAR,
    "JCB01": _EACH,
    "UTB01": _EACH,
    "GS01": _EACH,
    "GS02": _EACH,
    "GS03": _EACH,
    "SW01": _EACH,
    "SW02": _EACH,
    "SW03": _EACH,
    "OT01": _EACH,
    "OT02": _EACH,
    "OT03": _EACH,
    "ACO01": _EACH,
    "CLR01": _EACH,
    "CLR02": _EACH,
    "CLR03": _EACH,
    "PB01": _EACH,
    "CBR01": _EACH,
    "CBR02": _EACH,
    "CBR03": _EACH,
    "CBR04": _EACH,
    "CBR05": _EACH,
    # ---- plumbing ----
    "PCSP01": _STICK_3M,
    "PCSP02": _STICK_3M,
    "PDP01": _STICK_3M,
    "PDP02": _STICK_3M,
    "PDP03": _STICK_3M,
    "PVTB01": _EACH,
    "PVTB02": _EACH,
    "PVTO01": _EACH,
    "PVTO02": _EACH,
    "PVTO03": _EACH,
    "PVYB01": _EACH,
    "PVYB02": _EACH,
    "PVYO01": _EACH,
    "PVYO02": _EACH,
    "PVYO03": _EACH,
}

DISCRETE_KINDS: frozenset[str] = frozenset({"each", "stick", "bag"})


def spec_for(item_id: str) -> UnitSpec:
    """Raises KeyError for an unknown SKU - never guess a unit."""
    return UNIT_SPECS[item_id]
