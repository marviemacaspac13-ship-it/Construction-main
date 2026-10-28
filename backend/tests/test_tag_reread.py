from unittest.mock import Mock, patch

import numpy as np
import pytest

from scripts.probe_tag_reread import recognize, select


def region(name='r1', x=40, y=40, text='WG', score=.6):
    return dict(id=name,text=text,score=score,cx=x,cy=y,rotated=False,
                quad=[[x-8,y-4],[x+8,y-4],[x+8,y+4],[x-8,y+4]])


def test_selects_difficult_short_outputs_without_manual_targets():
    candidates=[region(),region('confident',y=80,score=.9),region('long',y=120,text='KITCHEN')]
    assert [p['id'] for p in select(candidates,[],(400,400,3))]==['r1']


def test_existing_count_excluded_but_nearby_distinct_region_survives():
    candidates=[region(),region('neighbor',y=64)]
    assert [p['id'] for p in select(candidates,[region()],(400,400,3))]==['neighbor']


def test_repeated_proposals_are_read_once():
    assert len(select([region(),region('repeat',x=41)],[],(400,400,3)))==1


@pytest.mark.parametrize('readings,accepted',[
    ([('WC',.8),('wc',.7)],True),
    ([('WC',.8),('WC',.49)],False),
    ([('WC',.8),('FD',.8)],False),
    ([('WG',.9),('WG',.9)],False),
])
def test_both_views_must_agree_above_unchanged_cutoff(readings,accepted):
    engine=Mock(use_angle_cls=False)
    engine.get_crop_img_list.return_value=[np.zeros((8,16,3),np.uint8)]
    engine.text_recognizer.return_value=(readings,0.0)
    with patch('scripts.probe_tag_reread._engine',return_value=engine):
        candidates,logs=recognize(np.zeros((100,100,3),np.uint8),[region()])
    assert bool(candidates)==accepted
    assert logs[0]['agreement']==accepted
