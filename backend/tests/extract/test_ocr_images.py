"""End-to-end OCR regression tests against the real plan images.

Slower than the rest of the suite (~2s per image, two OCR passes each), so
they are marked. Run just these with:  pytest -m ocr
Skip them with:                        pytest -m "not ocr"

They skip automatically when the plan images are absent.
"""

from pathlib import Path

import pytest

from app.extract.reader import read_plan

PLANS = Path(__file__).resolve().parents[1] / "fixtures" / "plans"

pytestmark = pytest.mark.ocr


@pytest.mark.skipif(not (PLANS / "01.png").exists(), reason="plan images not present")
def test_cad_wide_reads_exactly():
    ex = read_plan(str(PLANS / "01.png"))
    assert ex.units.unit == "mm"
    assert (round(ex.envelope_w_m, 2), round(ex.envelope_l_m, 2)) == (14.0, 11.0)
    assert len(ex.rooms_m) == 10
    assert all(c.ok for c in ex.chain_checks)
    assert len(ex.chain_checks) == 4
    assert ex.walls.total_m == pytest.approx(91.9)
    assert ex.confidence >= 0.9


@pytest.mark.skipif(not (PLANS / "03.png").exists(), reason="plan images not present")
def test_cad_square_reads_exactly():
    ex = read_plan(str(PLANS / "03.png"))
    assert ex.units.unit == "mm"
    assert (round(ex.envelope_w_m, 2), round(ex.envelope_l_m, 2)) == (11.5, 10.0)
    assert len(ex.rooms_m) == 6, [r.name for r in ex.rooms_m]
    assert all(c.ok for c in ex.chain_checks)
    assert ex.walls.total_m == pytest.approx(64.1)


@pytest.mark.skipif(not (PLANS / "02.jpg").exists(), reason="plan images not present")
def test_notebook_recovers_its_width_from_the_printed_overall():
    """OCR misses a segment of this plan top chain, which used to shrink it.

    The chain reads 390 + 370 = 760 against a printed 830, so the width came
    out 7.60 m instead of 8.30 and the area check flagged the building as
    108% accounted for. The overall is one read of one number and a chain can
    only lose segments, so the overall wins and the width is now exact.
    """
    ex = read_plan(str(PLANS / "02.jpg"))
    assert (round(ex.envelope_w_m, 2), round(ex.envelope_l_m, 2)) == (8.3, 13.5)
    assert ex.walls.total_m == pytest.approx(73.6)
    assert ex.area.accounted_ratio < 1.05


@pytest.mark.skipif(not (PLANS / "02.jpg").exists(), reason="plan images not present")
def test_the_recovered_width_is_not_passed_off_as_verified():
    """Right answer, unproven: the chain still does not close and says so."""
    ex = read_plan(str(PLANS / "02.jpg"))
    broken = [c for c in ex.chain_checks if not c.ok]
    assert len(broken) == 1
    assert broken[0].stated_total == 830
    assert broken[0].total == 760
    assert any("does not close" in w for w in ex.warnings())
    assert ex.confidence < 0.6


@pytest.mark.skipif(not (PLANS / "04.jpg").exists(), reason="plan images not present")
def test_unreadable_opening_tags_fall_back_to_an_assumption():
    """The schedule tags on this scan are not recoverable by OCR.

    Deducting nothing over-estimated masonry by ~10%. Assuming one door and
    one window per room is far closer, but it is an assumption and the
    extraction has to say so rather than present it as a measurement.
    """
    ex = read_plan(str(PLANS / "04.jpg"))
    assert ex.openings_assumed
    assert ex.doors == len(ex.rooms_m)
    assert ex.windows == len(ex.rooms_m)
    assert any("assumed from" in w for w in ex.warnings())
    assert not any("over-estimated" in w for w in ex.warnings())