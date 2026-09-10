"""Helpers shared by the per-plan-type rule modules."""

import math

from app.takeoff.constants import REBAR_KG_PER_M


def with_waste(quantity: float, waste: float) -> float:
    """Add a waste allowance expressed as a fraction (0.05 == 5%)."""
    return quantity * (1.0 + waste)


def bars_across(span_m: float, spacing_m: float) -> int:
    """Number of bars laid across a span at a given spacing, both ends included.

    A 3.0 m span at 0.60 m spacing is 5 gaps and therefore 6 bars.
    """
    if span_m <= 0:
        return 0
    return math.ceil(span_m / spacing_m) + 1


def rebar_mass_kg(item_id: str, total_length_m: float) -> float:
    """Mass of a given length of deformed bar. Raises KeyError for unknown bars."""
    return REBAR_KG_PER_M[item_id] * total_length_m
