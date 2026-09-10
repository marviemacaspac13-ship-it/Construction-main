"""Infer the drawing's unit from the magnitude of its dimensions.

Plans in this corpus state dimensions as bare numbers and never name the
unit: 14000 is millimetres, 1026 is centimetres, 830 is centimetres. The
inference is from magnitude, bounded by what a building can physically be,
and the result is always sanity-checked rather than trusted blindly
(trace-system-requirements.md section 2).
"""

from dataclasses import dataclass

# A building's longest plan dimension, in metres. Anything outside this is
# not a house and the inference should be treated as failed.
MIN_BUILDING_M = 3.0
MAX_BUILDING_M = 60.0

_SCALES = {"mm": 0.001, "cm": 0.01, "m": 1.0}


@dataclass(frozen=True)
class UnitInference:
    unit: str
    metres_per_unit: float
    confidence: float
    note: str

    def to_metres(self, value: float) -> float:
        return value * self.metres_per_unit


def infer_units(envelope_max: float) -> UnitInference:
    """Infer units from the largest overall (envelope) dimension.

    Use the envelope, not a room: a room of 5400 is ambiguous on its own,
    but an envelope of 14000 is unambiguously millimetres.
    """
    if envelope_max <= 0:
        return UnitInference("unknown", 0.0, 0.0, "no envelope dimension found")

    if envelope_max >= 3000:
        unit = "mm"
    elif envelope_max >= 300:
        unit = "cm"
    else:
        unit = "m"

    metres_per_unit = _SCALES[unit]
    result_m = envelope_max * metres_per_unit

    if MIN_BUILDING_M <= result_m <= MAX_BUILDING_M:
        confidence = 0.95
        note = f"{envelope_max:g} read as {unit} -> {result_m:.2f} m envelope"
    else:
        confidence = 0.2
        note = (
            f"{envelope_max:g} as {unit} gives {result_m:.2f} m, outside the "
            f"{MIN_BUILDING_M:g}-{MAX_BUILDING_M:g} m range a building can be"
        )

    return UnitInference(unit, metres_per_unit, confidence, note)
