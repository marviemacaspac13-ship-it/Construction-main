"""Printed-tag reads go through the same review as model proposals before pricing.

Without this, a plumbing scan priced whatever the tag reader counted whenever
the image models were off, failing or over quota - the one path in the app
where an unconfirmed count reached a price.
"""
import io
import json
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app import plumbing_vision as vision
from app.extract.ocr import TextBox
from app.main import app
from app.takeoff.contracts import EstimateInputSnapshot

client = TestClient(app)


@pytest.fixture
def image():
    buffer = io.BytesIO()
    Image.new('RGB', (120, 80), 'white').save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setenv('PLUMBING_VISION_ENABLED', 'false')


def tag(text, x, y):
    return TextBox(text, x, y, .9, False, quad=((x-5, y-5), (x+5, y-5), (x+5, y+5), (x-5, y+5)))


TAGS = [tag('WC', 30, 20), tag('LAV', 30, 50), tag('FD', 60, 40), tag('CO', 90, 60)]


def propose(image, boxes=TAGS):
    with patch.object(vision, 'read_tiled', return_value=boxes):
        result = client.post('/api/plumbing/proposals', files={'file': ('plan.png', image, 'image/png')})
    assert result.status_code == 200, result.text
    return result.json()


def test_unavailable_models_fall_back_to_reviewable_tag_proposals(image, disabled):
    result = propose(image)
    assert result['available'] is True
    assert result['provider'] == 'tags'
    assert result['receipt']
    assert [f['fixture_class'] for f in result['fixtures']] == ['WC', 'LAV', 'FD', 'CO']
    # The WC label spans x 25-35 of 120 px and y 15-25 of 80 px.
    assert result['fixtures'][0]['box_2d'] == pytest.approx([187.5, 208.33, 312.5, 291.67], abs=.01)


def test_failed_models_also_fall_back_to_tag_proposals(image, monkeypatch):
    monkeypatch.setenv('PLUMBING_VISION_ENABLED', 'true')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('PLUMBING_GEMINI_MODELS', 'first')
    with patch.object(vision, 'call_model', AsyncMock(side_effect=TimeoutError())):
        result = propose(image)
    assert result['provider'] == 'tags'
    assert result['attempts'] == [{'provider': 'gemini', 'model': 'first', 'outcome': 'timeout'}]


def test_no_tags_read_keeps_the_original_refusal(image, disabled):
    result = propose(image, [])
    assert result['available'] is False
    assert result['receipt'] is None


def test_one_label_read_twice_is_proposed_once(image, disabled):
    # The two OCR passes read one glyph as 'WC' and 'wC' at the same spot. The
    # review refuses overlapping boxes, so passing both would block every
    # confirmation; the old reader priced both. A different type is kept.
    twice = [tag('WC', 30, 20), TextBox('wC', 31, 20, .5, False, quad=((26, 15), (36, 15), (36, 25), (26, 25))),
             tag('FD', 31, 20)] + TAGS[1:]
    result = propose(image, twice)
    assert [f['fixture_class'] for f in result['fixtures']] == ['WC', 'LAV', 'FD', 'FD', 'CO']
    assert result['fixtures'][0]['uncertainty'] == 'Printed tag read as "WC".'


def test_too_few_tags_keeps_the_minimum_fixture_refusal(image, disabled):
    # One stray WC on an untagged sheet used to price at P1,744; offering it
    # for review would make that one click away. Cleanouts imply no material.
    result = propose(image, [tag('WC', 30, 20), tag('CO', 60, 40), tag('CO', 90, 60)])
    assert result['available'] is False
    assert result['receipt'] is None


def test_confirmed_tag_review_prices_every_class_without_rereading(image, disabled, catalog):
    result = propose(image)
    kept = [f for f in result['fixtures'] if f['fixture_class'] != 'CO']
    added = {'id': 'added-1', 'fixture_class': 'LAV', 'box_2d': [700, 700, 750, 750], 'uncertainty': None}
    review = {'receipt': result['receipt'], 'confirmed': True, 'fixtures': kept + [added]}
    with patch('app.main.read_tiled', side_effect=AssertionError('reviewed tags must not be re-read')), \
         patch('app.main.load_catalog', return_value=catalog):
        priced = client.post('/api/estimate/image', files={'file': ('plan.png', image, 'image/png')},
                             data={'plan_type': 'Plumbing Plan', 'fixture_review': json.dumps(review)})
    assert priced.status_code == 200, priced.text
    plan = EstimateInputSnapshot.model_validate(priced.json()['original_input']).plan
    assert {k: v for k, v in plan.fixture_tags.items() if v} == {'water_closet': 1, 'floor_drain': 1, 'lavatory': 2}
    assert plan.fixture_review.provider == 'tags'
    assert plan.fixture_review.prompt_version == 'plumbing-tags-v1'
    assert any('printed fixture tags' in s and 'explicitly reviewed' in s
               for s in priced.json()['estimate']['assumptions'])


def test_model_review_cannot_submit_classes_it_does_not_replace(image, monkeypatch):
    monkeypatch.setenv('PLUMBING_VISION_ENABLED', 'true')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('PLUMBING_GEMINI_MODELS', 'first')
    body = {'fixtures': [{'id': 'WC-1', 'fixture_class': 'WC', 'box_2d': [100, 100, 200, 200], 'uncertainty': None}],
            'limitations': []}
    with patch.object(vision, 'call_model', AsyncMock(return_value=json.dumps(body))):
        result = client.post('/api/plumbing/proposals', files={'file': ('plan.png', image, 'image/png')}).json()
    assert result['provider'] == 'gemini'
    # A floor drain boxed in a WC/LAV review would be dropped silently while
    # the OCR floor-drain count stayed in the estimate.
    drain = {'id': 'added-1', 'fixture_class': 'FD', 'box_2d': [400, 400, 450, 450], 'uncertainty': None}
    review = {'receipt': result['receipt'], 'confirmed': True, 'fixtures': result['fixtures'] + [drain]}
    with pytest.raises(HTTPException):
        vision.validate_review(json.dumps(review), image, 'test-user')
