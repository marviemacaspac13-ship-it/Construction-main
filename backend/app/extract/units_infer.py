"""Infer the drawing's unit from the magnitude of its dimensions.

Plans in this corpus state dimensions as bare numbers and never name the
unit: 14000 is millimetres, 1026 is centimetres, 830 is centimetres. The
inference is from magnitude, bounded by what a building can physically be,
and the result is always sanity-checked rather than trusted blindly
(trace-system-requirements.md section 2).
"""

import re
from dataclasses import dataclass

# A building's longest plan dimension, in metres. Anything outside this is
# not a house and the inference should be treated as failed.
MIN_BUILDING_M = 3.0
MAX_BUILDING_M = 60.0

# Feet-and-inches notation, which this reader does not support.
#
# Every plan it was built for states bare metric numbers - 14000 mm, 1026
# cm - and the whole unit inference above rests on their MAGNITUDE. An
# imperial drawing breaks that at the root: 94 is ninety-four feet, not
# ninety-four of anything the scales below know, and a room written
# "13-2x17-2" is 13 ft 2 in by 17 ft 2 in, not 132 by 172 of anything.
#
# It already fails safely - the notation does not parse, so no dimension is
# invented and the plan is refused. These patterns exist only so the
# refusal can say WHY, because "could not read enough of the plan" sends
# someone hunting for a better scan of a drawing that was never readable.
#
#   16'-0"   12' 6"   94'        foot mark, with or without inches
#   13-2x17-2                    feet-inches pair, no marks at all
#   13x2x17x2                    the same pair AFTER separator repair
#
# That third form is the one that actually fires on this corpus, and it is
# worth understanding why. The separator repair turns any punctuation
# between two digits into an `x` - the fix that lets `324.240` and `324:240`
# read as rooms - so by the time these texts are seen, `13-2x17-2` has
# become `13x2x17x2` and the dashes that marked it as imperial are gone.
#
# A FOUR-part dimension is therefore the signature: a metric room is
# `324x240`, two parts. Four parts joined by `x` is a feet-inches pair with
# its separators eaten, and it is also exactly why these plans fail safely
# - four parts do not parse as a width and a length, so no size is
# invented.
_IMPERIAL_PATTERNS = (
    re.compile(r"\d+\s*'"),                       # 94'   16'-0"
    re.compile(r'\d+\s*"'),                       # 7-9"
    re.compile(r"\d{1,2}-\d{1,2}\s*[xX]\s*\d{1,2}-\d{1,2}"),  # 13-2x17-2
    re.compile(r"\d{1,2}[xX]\d{1,2}[xX]\d{1,2}[xX]\d{1,2}"),  # 13x2x17x2
)

# How many imperial-looking tokens before it is the drawing rather than a
# stray apostrophe in a room name. Two is enough: a plan dimensioned this
# way carries one per room.
IMPERIAL_MIN_HITS = 2


def looks_imperial(texts: list[str]) -> bool:
    """True when the drawing appears to be dimensioned in feet and inches.

    Asked only to explain a refusal, never to change a reading - a plan
    that reads successfully is metric by construction, because nothing
    imperial parses into a dimension in the first place.
    """
    hits = sum(
        1 for t in texts if t and any(p.search(t) for p in _IMPERIAL_PATTERNS)
    )
    return hits >= IMPERIAL_MIN_HITS

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
