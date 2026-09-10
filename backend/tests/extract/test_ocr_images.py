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
def test_notebook_read_is_wrong_and_says_so():
    """The hand-drawn plan misreads its width - the area check must catch it."""
    ex = read_plan(str(PLANS / "02.jpg"))
    assert ex.area.accounted_ratio > 1.05
    assert any("more than the whole building" in w for w in ex.warnings())
    assert ex.confidence < 0.85


@pytest.mark.skipif(not (PLANS / "04.jpg").exists(), reason="plan images not present")
def test_missing_opening_tags_are_reported():
    """Openings missed by OCR inflate masonry; that must not pass silently."""
    ex = read_plan(str(PLANS / "04.jpg"))
    assert ex.windows == 0
    assert any("over-estimated" in w for w in ex.warnings())