"""Renaming a detection from the word printed beside it.

The logic is tested against constructed boxes so the geometry is visible
and it runs fast. One `ocr`-marked test reads the real electrical plan,
because the reason this module exists is that `05.png` has an AC outlet on
it that the matcher has always sold as a general-purpose one.
"""

from pathlib import Path

import cv2
import pytest

from app.extract.ocr import TextBox
from app.schemas import Detection
from app.vision.relabel import ADJACENT_MAX_FRAC, relabel_from_adjacent_text

SHAPE = (497, 641, 3)  # 05.png
LIMIT = max(SHAPE[:2]) * ADJACENT_MAX_FRAC  # ~38 px

PLANS = Path(__file__).parent / "fixtures" / "plans"


def det(label: str, cx: float, cy: float) -> Detection:
    return Detection(label=label, confidence=0.8, bbox=[cx - 9, cy - 9, cx + 9, cy + 9])


def box(text: str, cx: float, cy: float) -> TextBox:
    return TextBox(text=text, cx=cx, cy=cy, score=0.8, rotated=False)


def labels(detections) -> list[str]:
    return [d.label for d in detections]


# --- the thing it is for ------------------------------------------------

def test_a_word_beside_an_outlet_renames_it():
    out = relabel_from_adjacent_text([det("OT01", 45, 160)], [box("ACU", 60, 132)], SHAPE)
    assert labels(out) == ["ACO01"]


def test_the_original_list_is_not_modified():
    detections = [det("OT01", 45, 160)]
    relabel_from_adjacent_text(detections, [box("ACU", 60, 132)], SHAPE)
    assert labels(detections) == ["OT01"]


# --- the trap this exists to avoid --------------------------------------

def test_a_room_label_cannot_rename_anything():
    """The whole safety argument, in one test.

    Measured on `05.png`: ACU sits 32 px from its outlet, BEDROOM1 sits
    40 px from a ceiling outlet, and TOILET & BATH sits 23 px from another
    - CLOSER than the one real example. A nearest-text-wins rule would
    label a ceiling receptacle "TOILET & BATH".
    """
    boxes = [box("TOILET &BATH", 512, 70), box("BEDROOM1", 92, 100), box("KITCHEN", 511, 190)]
    detections = [det("CLR01", 512, 53), det("CLR01", 92, 78), det("CLR01", 511, 177)]
    assert labels(relabel_from_adjacent_text(detections, boxes, SHAPE)) == ["CLR01"] * 3


def test_a_known_word_cannot_rename_the_wrong_kind_of_symbol():
    """ACU renames a wall outlet. It must never touch a ceiling receptacle."""
    out = relabel_from_adjacent_text([det("CLR01", 45, 160)], [box("ACU", 60, 132)], SHAPE)
    assert labels(out) == ["CLR01"]


def test_one_word_claims_one_symbol():
    """A single ACU must not convert a cluster into a row of AC points."""
    detections = [det("OT01", 60, 140), det("OT01", 66, 146), det("OT01", 72, 152)]
    out = relabel_from_adjacent_text(detections, [box("ACU", 60, 132)], SHAPE)
    assert sorted(labels(out)) == ["ACO01", "OT01", "OT01"]


def test_the_nearest_symbol_wins():
    detections = [det("OT01", 300, 300), det("OT01", 62, 135)]
    out = relabel_from_adjacent_text(detections, [box("ACU", 60, 132)], SHAPE)
    assert labels(out) == ["OT01", "ACO01"]


# --- distance -----------------------------------------------------------

def test_a_word_too_far_away_describes_nothing():
    far = box("ACU", 45 + LIMIT + 5, 160)
    assert labels(relabel_from_adjacent_text([det("OT01", 45, 160)], [far], SHAPE)) == ["OT01"]


def test_the_window_is_a_fraction_of_the_image_not_a_pixel_count():
    """These sheets run 0.16 MP to 3.15 MP. A fixed radius means one thing
    on a thumbnail and another on a full-size export."""
    small = (349, 497, 3)
    large = (1536, 2048, 3)
    at = 100  # px from the symbol
    near = [box("ACU", 45 + at, 160)]
    assert labels(relabel_from_adjacent_text([det("OT01", 45, 160)], near, small)) == ["OT01"]
    assert labels(relabel_from_adjacent_text([det("OT01", 45, 160)], near, large)) == ["ACO01"]


# --- degenerate input ---------------------------------------------------

@pytest.mark.parametrize(
    "detections,boxes,shape",
    [([], [box("ACU", 60, 132)], SHAPE), ([det("OT01", 45, 160)], [], SHAPE),
     ([det("OT01", 45, 160)], [box("ACU", 60, 132)], ())],
)
def test_nothing_to_do_is_not_an_error(detections, boxes, shape):
    assert relabel_from_adjacent_text(detections, boxes, shape) == detections


def test_leader_line_punctuation_is_stripped_like_any_other_tag():
    out = relabel_from_adjacent_text([det("OT01", 45, 160)], [box("+ acu", 60, 132)], SHAPE)
    assert labels(out) == ["ACO01"]


# --- against the real plan ----------------------------------------------

@pytest.mark.ocr
@pytest.mark.skipif(not (PLANS / "05.png").exists(), reason="plan image not present")
def test_the_real_acu_on_05_is_found_and_nothing_else_moves():
    """One of 28 detections is renamed, and only one.

    The hand count says 14 convenience outlets, one of which is the ACU
    point, so exactly one rename is the correct outcome here.
    """
    from app.extract.tags import read_tiled
    from app.vision.preprocess import preprocess_image
    from app.vision.template_match import match_templates

    raw = (PLANS / "05.png").read_bytes()
    detections = match_templates(preprocess_image(raw))
    plain = cv2.imread(str(PLANS / "05.png"))

    out = relabel_from_adjacent_text(detections, read_tiled(plain), plain.shape)

    assert labels(out).count("ACO01") == 1
    # Everything else keeps the label the matcher gave it.
    assert len(out) == len(detections)
    assert labels(out).count("CLR01") == labels(detections).count("CLR01")
