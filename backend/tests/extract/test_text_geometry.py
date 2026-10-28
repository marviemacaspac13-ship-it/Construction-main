from unittest.mock import patch

import numpy as np
import pytest

from app.extract.ocr import TextBox, _boxes_from, read_region
from scripts.probe_tag_geometry import deduplicate, overlap


def test_rotated_vertices_return_to_original_image_coordinates():
    result = [([[10, 20], [30, 20], [30, 28], [10, 28]], 'WC', .9)]
    box = _boxes_from(result, 100, True)[0]
    assert box.quad == ((20, 89), (20, 69), (28, 69), (28, 89))
    assert (box.cx, box.cy) == (24, 79)


def test_tile_translation_preserves_both_passes_geometry():
    result = [([[2, 3], [10, 3], [10, 7], [2, 7]], 'WC', .9)]
    with patch('app.extract.ocr._engine') as engine:
        engine.return_value.return_value = (result, None)
        upright, rotated = read_region(np.zeros((100, 120, 3), np.uint8), 20, 30, 60, 70)
    assert upright.quad == ((22, 33), (30, 33), (30, 37), (22, 37))
    assert rotated.quad == ((23, 67), (23, 59), (27, 59), (27, 67))
    assert (upright.cx, upright.cy) == (26, 35)
    assert (rotated.cx, rotated.cy) == (25, 63)


def observation(name, tag='water_closet', x=0, y=0, scale=1, score=.9):
    return dict(id=name, tag=tag, score=score,
                quad=[[(x + dx) * scale, (y + dy) * scale]
                      for dx, dy in ((0, 0), (16, 0), (16, 8), (0, 8))])


@pytest.mark.parametrize('scale', [.25, .5, 1, 2])
def test_overlap_merges_duplicate_but_preserves_nearby_real_tag_at_every_scale(scale):
    items = [observation('a', scale=scale), observation('b', x=1, scale=scale, score=.8),
             observation('neighbor', y=24, scale=scale),
             observation('other-class', tag='floor_drain', scale=scale)]
    kept, removed = deduplicate(items)
    assert {o['id'] for o in kept} == {'a', 'neighbor', 'other-class'}
    assert [o['id'] for o in removed] == ['b']


def test_old_center_only_boxes_remain_valid_and_are_not_guessed_at():
    assert TextBox('WC', 1, 2, .9, False).quad is None
    kept, removed = deduplicate([dict(id=str(i), tag='WC', score=.9) for i in range(2)])
    assert len(kept) == 2 and not removed


@pytest.mark.parametrize('quad', [None, [[1, 1]] * 4, [[float('nan'), 1]] * 4])
def test_missing_or_degenerate_geometry_cannot_suppress_a_tag(quad):
    assert overlap(dict(quad=quad), observation('valid')) == 0
