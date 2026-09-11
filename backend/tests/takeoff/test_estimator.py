"""Pricing: rounding policy, unmatched policy, provenance.

The rounding rule is the reason this file exists: you cannot buy 4.2 pipes
or 11.025 bags of cement, but you can buy 23.46 metres of wire.
"""

import pytest

from app.takeoff.bom import BomLine
from app.takeoff.estimator import estimate_from_bom
from app.takeoff.params import EstimatingParams


def price(bom, catalog, plan_type="Floor Plan"):
    return estimate_from_bom(bom, catalog, plan_type, EstimatingParams())


def line(item_id, quantity, rule="r", derivation="d"):
    return BomLine(item_id=item_id, quantity=quantity, rule=rule, derivation=derivation)


# --- rounding ------------------------------------------------------------

@pytest.mark.parametrize(
    "item_id,raw,expected,why",
    [
        ("PCSP01", 4.2, 5, "stick - cannot buy 4.2 pipes"),
        ("CMT01", 11.025, 12, "bag - cannot buy a fraction of a sack"),
        ("CHB01", 393.75, 394, "each - whole blocks"),
        ("DB01", 142.9, 143, "stick - whole 6 m lengths"),
    ],
)
def test_discrete_quantities_round_up(catalog, item_id, raw, expected, why):
    result = price([line(item_id, raw)], catalog)
    assert result.line_items[0].quantity == expected, why


@pytest.mark.parametrize(
    "item_id,raw,expected",
    [
        ("ELW04", 23.456, 23.46),   # linear metres
        ("SND02", 4.67625, 4.68),   # cubic metres
        ("GI01", 7.93542, 7.94),    # kilograms
    ],
)
def test_continuous_quantities_keep_two_decimals(catalog, item_id, raw, expected):
    result = price([line(item_id, raw)], catalog)
    assert result.line_items[0].quantity == pytest.approx(expected)


def test_an_exact_whole_number_does_not_get_rounded_up(catalog):
    """ceil(5.0) must stay 5, not become 6."""
    assert price([line("PCSP01", 5.0)], catalog).line_items[0].quantity == 5


def test_floating_point_noise_does_not_inflate_a_whole_number(catalog):
    """5.0000000001 sticks is 5, not 6 - the rounding guards against this."""
    assert price([line("PCSP01", 5.0000000001)], catalog).line_items[0].quantity == 5


def test_line_total_uses_the_rounded_quantity(catalog):
    result = price([line("PCSP01", 4.2)], catalog)
    li = result.line_items[0]
    assert li.quantity == 5
    assert li.line_total == pytest.approx(5 * 72.0)


# --- totals --------------------------------------------------------------

def test_grand_total_sums_line_totals(catalog):
    result = price([line("CHB01", 10.0), line("CMT01", 2.0)], catalog)
    assert result.grand_total == pytest.approx(10 * 12.0 + 2 * 261.0)


def test_lines_are_sorted_by_line_total_descending(catalog):
    result = price([line("CHB01", 1.0), line("CMT01", 1.0)], catalog)
    assert [li.item_id for li in result.line_items] == ["CMT01", "CHB01"]


def test_empty_bom_gives_zero_total(catalog):
    result = price([], catalog)
    assert result.grand_total == 0.0
    assert result.line_items == []


# --- unmatched policy ----------------------------------------------------

def test_unpriced_items_are_flagged_never_dropped(catalog):
    """A rule asking for a SKU with no catalog row must surface, not vanish."""
    result = price([line("GHOST1", 3.0), line("CHB01", 10.0)], catalog)
    assert [u.item_id for u in result.unpriced] == ["GHOST1"]
    assert [li.item_id for li in result.line_items] == ["CHB01"]
    assert result.grand_total == pytest.approx(120.0)


def test_an_unpriced_item_keeps_its_derivation_for_review(catalog):
    result = price([line("GHOST1", 3.0, derivation="because reasons")], catalog)
    assert result.unpriced[0].derivation == "because reasons"


# --- merging and provenance ---------------------------------------------

def test_lines_for_the_same_sku_are_summed_before_pricing(catalog):
    """Mortar cement and concrete cement are one purchase."""
    result = price(
        [
            line("CMT01", 2.0, rule="structural.laying_mortar", derivation="from mortar"),
            line("CMT01", 3.5, rule="structural.concrete", derivation="from concrete"),
        ],
        catalog,
    )
    assert len(result.line_items) == 1
    li = result.line_items[0]
    assert li.quantity == 6  # ceil(5.5) bags
    assert "from mortar" in li.derivation
    assert "from concrete" in li.derivation
    assert li.rule == "structural.concrete+structural.laying_mortar"


def test_response_carries_provenance(catalog):
    result = price([line("CHB01", 10.0, rule="structural.chb_blocks", derivation="why")], catalog)
    assert result.rules_version
    assert result.priced_at
    assert result.plan_type == "Floor Plan"
    assert result.line_items[0].rule == "structural.chb_blocks"
    assert result.line_items[0].derivation == "why"
    assert any("Wall height" in a for a in result.assumptions)


def test_catalog_display_fields_are_carried_through(catalog):
    li = price([line("CHB02", 10.0)], catalog).line_items[0]
    assert li.item_name == "Concrete Hollow Blocks"
    assert li.unit == "6 inches / Per Pc"
    assert li.unit_price == 18.0


def test_a_null_unit_is_tolerated(catalog):
    """PB01 has no unit string in the catalog."""
    assert price([line("PB01", 1.0)], catalog).line_items[0].unit is None