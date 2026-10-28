"""Stage attribution must distinguish missing proposals from rejected readings."""
import pytest

from scripts.trace_missed_tags import diagnose


TARGET = dict(id='wc-1', tag='water_closet', cx=20, cy=30)


def proposal(text='WC', score=.9, **kwargs):
    return dict(text=text, score=score, passes_confidence=score >= .5,
                cx=20, cy=30, quad=[[15, 25], [25, 25], [25, 35], [15, 35]], **kwargs)


@pytest.mark.parametrize('raw,before,merged,final,reason', [
    ([], [], [], [], 'no_local_detector_proposal'),
    ([proposal('wC', .4)], [], [], [], 'recognition_confidence_filter'),
    ([proposal('we')], [proposal('we')], [proposal('we')], [], 'recognition_or_text_grouping'),
    ([proposal()], [proposal()], [], [], 'exact_string_merge'),
    ([proposal()], [proposal()], [proposal()], [], 'legend_filter'),
    ([proposal()], [proposal()], [proposal()], [proposal()], 'recovered'),
])
def test_stage_attribution(raw, before, merged, final, reason):
    assert diagnose(TARGET, raw, before, merged, final)['reason'] == reason


def test_a_nearby_different_tag_does_not_explain_a_miss():
    other = dict(proposal(), cx=20, cy=55, quad=[[15, 50], [25, 50], [25, 60], [15, 60]])
    result = diagnose(TARGET, [other], [other], [other], [other])
    assert result['reason'] == 'no_local_detector_proposal'


def test_large_box_covering_center_is_grouping_evidence_not_correct_recognition():
    grouped = dict(proposal('WC FD'), cx=40, quad=[[15, 25], [65, 25], [65, 35], [15, 35]])
    assert diagnose(TARGET, [grouped], [], [], [])['reason'] == 'recognition_or_text_grouping'


def test_readable_spaced_cleanout_is_a_parser_loss_not_an_ocr_misread():
    target = dict(TARGET, tag='cleanout')
    box = proposal('C. O.')
    assert diagnose(target, [box], [box], [box], [])['reason'] == 'tag_parser_internal_whitespace'
