"""The second look: re-reading around a room label that found no dimensions.

The text detector proposes different regions on a small crop than on a busy
full page, so dimension text it walks past on the whole plan is often read
at the same scale once the page around it is gone. That is the whole trick -
it is not a resolution problem and upscaling is not involved.

What makes it safe is what it throws away. These tests are mostly about the
guards, because an unguarded rescue invented a second kitchen out of a
truncated re-read of the first one.
"""

import pytest

from app.extract.ocr import TextBox
from app.extract import reader
from app.extract.reader import rescue_dimensions, unpaired_labels


def box(text: str, cx: float, cy: float, score: float = 0.8) -> TextBox:
    return TextBox(text=text, cx=cx, cy=cy, score=score, rotated=False)


@pytest.fixture
def crop_returns(monkeypatch):
    """Stub read_region, recording the crops asked for."""
    calls: list[tuple[int, int, int, int]] = []

    def install(boxes: list[TextBox]):
        def fake(image, x1, y1, x2, y2):
            calls.append((x1, y1, x2, y2))
            return boxes
        monkeypatch.setattr(reader, "read_region", fake)
        return calls

    return install


# --- spotting the gap ---------------------------------------------------

def test_a_label_with_a_dimension_under_it_is_paired():
    boxes = [box("KITCHEN", 100, 100), box("324x240", 100, 130)]
    assert unpaired_labels(boxes) == []


def test_a_label_with_nothing_under_it_is_unpaired():
    boxes = [box("WIC", 100, 100), box("324x240", 500, 130)]
    assert [b.text for b in unpaired_labels(boxes)] == ["WIC"]


def test_a_dimension_above_the_label_does_not_count():
    """Room labels sit above their size, never below it."""
    boxes = [box("WIC", 100, 130), box("192x138", 100, 100)]
    assert [b.text for b in unpaired_labels(boxes)] == ["WIC"]


def test_numbers_and_dimensions_are_not_labels():
    boxes = [box("1026", 100, 100), box("324x240", 300, 300)]
    assert unpaired_labels(boxes) == []


# --- what comes back ----------------------------------------------------

def test_a_dimension_under_the_trigger_label_is_kept(crop_returns):
    crop_returns([box("192x138", 100, 130)])
    out = rescue_dimensions(None, [box("WIC", 100, 100)])
    assert "192x138" in [b.text for b in out]


def test_a_dimension_that_does_not_pair_with_the_trigger_is_dropped(crop_returns):
    """The crop is a window onto other rooms too; only the gap is being filled.

    This is the case that invented a second kitchen: a crop taken around a
    stray UP label re-read a neighbouring room size and offered it back.
    """
    crop_returns([box("324x2", 20, 20)])
    out = rescue_dimensions(None, [box("UP", 100, 100)])
    assert [b.text for b in out] == ["UP"]


def test_a_dimension_already_known_here_is_dropped(crop_returns):
    """The full-page pass saw more context, so it wins every tie.

    A narrow case by construction: the known dimension has to sit just
    outside the label pairing window - 72 px below it, against a limit of
    70 - while the rescued re-read of the same text lands just inside at
    50 px. Otherwise the label would have paired and never triggered a
    crop at all.
    """
    existing = [box("UP", 100, 100), box("324x240", 100, 172)]
    assert [b.text for b in unpaired_labels(existing)] == ["UP"]

    crop_returns([box("324x2", 100, 150)])
    out = rescue_dimensions(None, existing)
    assert "324x2" not in [b.text for b in out]


def test_labels_found_in_the_crop_are_not_taken_back(crop_returns):
    """Only dimensions. Letting labels in would duplicate what is placed better."""
    crop_returns([box("BATH", 100, 120), box("192x138", 100, 130)])
    out = rescue_dimensions(None, [box("WIC", 100, 100)])
    assert sorted(b.text for b in out) == ["192x138", "WIC"]


def test_the_original_boxes_all_survive(crop_returns):
    crop_returns([])
    original = [box("WIC", 100, 100), box("1026", 300, 40), box("HALL", 200, 200)]
    out = rescue_dimensions(None, original)
    assert sorted(b.text for b in out) == ["1026", "HALL", "WIC"]


# --- cost ---------------------------------------------------------------

def test_a_clean_plan_never_reads_the_image_again(crop_returns):
    """Two of the four sample plans have no unpaired labels at all."""
    calls = crop_returns([])
    rescue_dimensions(None, [box("KITCHEN", 100, 100), box("324x240", 100, 130)])
    assert calls == []


def test_one_crop_is_taken_per_unpaired_label(crop_returns):
    calls = crop_returns([])
    rescue_dimensions(None, [box("WIC", 100, 100), box("STORE", 400, 400)])
    assert len(calls) == 2


def test_the_crop_is_centred_on_the_label(crop_returns):
    calls = crop_returns([])
    rescue_dimensions(None, [box("WIC", 200, 300)])
    x1, y1, x2, y2 = calls[0]
    assert (x1 + x2) / 2 == 200
    assert (y1 + y2) / 2 == 300
    assert x2 - x1 == y2 - y1 == 2 * reader.RESCUE_PAD
