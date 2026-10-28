from dataclasses import replace
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from app import main
from app.extract.ocr import TextBox
from app.extract.tags import count_tags, normalise_tag, tally
from app.takeoff.constants import FIXTURE_TAG_PATTERNS


def box(text, x=100, y=100, score=.9):
    return TextBox(text, x, y, score, False,
                   ((x-10, y-5), (x+10, y-5), (x+10, y+5), (x-10, y+5)))


@pytest.mark.parametrize('text', ['CO', 'C.O.', 'C. O.', 'c. o.', 'C O', 'C . O .', 'C\t.\tO', '+ C. O. *'])
def test_complete_cleanout_variants_are_recognized(text):
    assert tally(count_tags([box(text)], FIXTURE_TAG_PATTERNS)) == {'cleanout': 1}


@pytest.mark.parametrize('text', ['FCO', 'F CO', 'WCO', 'CCO', 'COST', 'CO2', 'C O 2',
                                 'CO FD', 'C.O. CLEANOUT', 'W C', 'F D', 'C\nO'])
def test_other_words_subtypes_and_combined_labels_are_not_repaired(text):
    assert tally(count_tags([box(text)], FIXTURE_TAG_PATTERNS)) == {}


def test_spaced_legend_entry_is_still_excluded():
    boxes = [box('C. O.', 1161, 224), box('CLEANOUT', 1260, 224), box('C. O.', 300, 400)]
    result = count_tags(boxes, FIXTURE_TAG_PATTERNS, (650, 1356, 3))
    assert result['cleanout'].count == 1
    assert result['cleanout'].boxes[0].cx == 300


def test_duplicate_cleanout_variants_count_once_and_keep_original_evidence():
    best = box('C. O.', score=.9)
    result = count_tags([box('CO', x=101, score=.8), best], FIXTURE_TAG_PATTERNS)
    assert result['cleanout'].boxes == (best,)
    assert best.text == 'C. O.'


@pytest.mark.parametrize('scale', [.25, .5, 1, 2])
def test_nearby_distinct_cleanouts_survive_at_each_scale(scale):
    original = [box('C.O.', y=100), box('C. O.', y=124)]
    scaled = [replace(b, cx=b.cx*scale, cy=b.cy*scale,
                      quad=tuple((x*scale,y*scale) for x,y in b.quad)) for b in original]
    assert count_tags(scaled, FIXTURE_TAG_PATTERNS)['cleanout'].count == 2


def test_missing_geometry_does_not_authorize_merging():
    boxes = [replace(box('CO'), quad=None), replace(box('C. O.'), quad=None)]
    assert count_tags(boxes, FIXTURE_TAG_PATTERNS)['cleanout'].count == 2


def test_cleanouts_still_cannot_satisfy_pricing_floor():
    image = np.full((300,300,3), 255, np.uint8)
    raw = cv2.imencode('.png', image)[1].tobytes()
    with patch.object(main, 'read_tiled', return_value=[box('C. O.', y=y) for y in (50,100,150,200)]):
        with pytest.raises(main.HTTPException) as error:
            main._read_plumbing(raw, 'Plumbing Plan')
    assert error.value.status_code == 422
