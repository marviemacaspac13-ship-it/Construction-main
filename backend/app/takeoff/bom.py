"""Bill of Materials lines, in purchase units, with full provenance.

`derivation` is the audit trail: it must state the numbers that produced
the quantity, so an estimator can check the arithmetic by hand.
"""

from collections import defaultdict

from pydantic import BaseModel, Field


class BomLine(BaseModel):
    item_id: str
    quantity: float  # in the SKU's purchase unit, before rounding
    rule: str  # e.g. "structural.chb_blocks"
    derivation: str  # e.g. "28.11 m^2 of 6in wall x 12.5 pcs/m^2 + 5% waste"
    inputs: dict[str, float] = Field(default_factory=dict)


def merge_bom(lines: list[BomLine]) -> list[BomLine]:
    """Sum lines for the same SKU, preserving every derivation.

    Drops zero-quantity lines. Result is sorted by item_id so output is
    stable across runs.
    """
    totals: dict[str, float] = defaultdict(float)
    rules: dict[str, set[str]] = defaultdict(set)
    derivations: dict[str, list[str]] = defaultdict(list)
    inputs: dict[str, dict[str, float]] = defaultdict(dict)

    for line in lines:
        if line.quantity <= 0:
            continue
        totals[line.item_id] += line.quantity
        rules[line.item_id].add(line.rule)
        derivations[line.item_id].append(line.derivation)
        inputs[line.item_id].update(line.inputs)

    return [
        BomLine(
            item_id=item_id,
            quantity=totals[item_id],
            rule="+".join(sorted(rules[item_id])),
            derivation="; ".join(derivations[item_id]),
            inputs=inputs[item_id],
        )
        for item_id in sorted(totals)
    ]
