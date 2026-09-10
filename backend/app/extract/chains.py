"""Margin dimension chains, and the checksum that validates an OCR read.

A plan's edge carries a run of segment dimensions plus a stated overall.
The segments sum to the overall - so a misread digit breaks the sum and is
detectable without asking anyone. This is the confidence signal that makes
a zero-input estimate defensible.

Two complications seen in real plans:
  - a chain may repeat a running total alongside the segments (cumulative
    dimensioning). Summing those double-counts.
  - hand-dimensioned plans round, so 318+360+215+132 = 1025 against a
    stated 1026. The check needs a tolerance, not equality.
"""

from dataclasses import dataclass, field


@dataclass
class ChainCheck:
    stated_total: float
    values: list[float]
    kept: list[float] = field(default_factory=list)
    dropped_cumulative: list[float] = field(default_factory=list)
    total: float = 0.0
    ok: bool = False
    error: float = 0.0

    @property
    def relative_error(self) -> float:
        if self.stated_total == 0:
            return 0.0
        return abs(self.error) / abs(self.stated_total)


def drop_cumulative(values: list[float], tol: float = 1.0) -> tuple[list[float], list[float]]:
    """Remove running-total annotations from a chain of segments.

    A value equal to the sum of everything before it is a cumulative
    marker, not another segment.
    """
    kept: list[float] = []
    dropped: list[float] = []
    running = 0.0
    for value in values:
        if kept and abs(value - running) <= tol:
            dropped.append(value)
            continue
        kept.append(value)
        running += value
    return kept, dropped


def validate_chain(
    values: list[float],
    stated_total: float,
    rel_tol: float = 0.005,
    abs_tol: float = 2.0,
) -> ChainCheck:
    """Check that a chain of segment dimensions sums to its stated overall."""
    check = ChainCheck(stated_total=stated_total, values=list(values))
    check.kept, check.dropped_cumulative = drop_cumulative(values)
    check.total = sum(check.kept)
    check.error = check.total - stated_total
    tolerance = max(abs_tol, abs(stated_total) * rel_tol)
    check.ok = abs(check.error) <= tolerance
    return check


def confidence_from_checks(checks: list[ChainCheck]) -> float:
    """Overall extraction confidence from however many chains were read.

    Every chain is an independent witness. Two agreeing chains is already
    strong; none is a coin toss.
    """
    if not checks:
        return 0.0
    passed = sum(1 for c in checks if c.ok)
    ratio = passed / len(checks)
    # More chains that agree -> more confidence, saturating around four.
    weight = min(len(checks), 4) / 4.0
    return round(0.5 * ratio + 0.5 * ratio * weight, 3)
