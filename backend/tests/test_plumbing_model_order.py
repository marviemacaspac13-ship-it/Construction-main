"""Plumbing tries the accurate fast model first and gives each model 60 s.

Measured on 30 Oct 2026 with prompt v2 (backend/datasets/plumbing-prompt-v2-flash-2026-10-30):
3.6, 3.7 and 3.8 Flash all read the sample sheets exactly, box for box, but only 3.6 Flash
answered inside 30 s (14 s). 3.7 and 3.8 Flash need 45-55 s, so at the old 30 s limit an
overloaded 3.6 Flash fell through to 2.5 Flash, whose boxes drift off their fixtures.
"""
import asyncio
import io
import json
from unittest.mock import AsyncMock, patch

from PIL import Image

from app import plumbing_vision as vision
from app.plan_assets import inspect_image


def test_without_a_setting_plumbing_tries_the_accurate_fast_model_first(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-not-a-real-key')
    monkeypatch.delenv('PLUMBING_GEMINI_MODELS', raising=False)
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    assert [m for _, m in vision.configured_models()] == [
        'gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-2.5-flash',
        'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']


def test_each_model_gets_sixty_seconds(monkeypatch):
    monkeypatch.setenv('PLUMBING_VISION_ENABLED', 'true')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('PLUMBING_GEMINI_MODELS', 'first')
    buffer = io.BytesIO()
    Image.new('RGB', (120, 80), 'white').save(buffer, format='PNG')
    raw = buffer.getvalue()
    limits = []
    real_wait_for = asyncio.wait_for

    async def recording_wait_for(awaitable, timeout):
        limits.append(timeout)
        return await real_wait_for(awaitable, timeout)

    body = json.dumps({'fixtures': [{'id': 'a', 'fixture_class': 'WC', 'box_2d': [1, 1, 50, 50],
                                     'uncertainty': None}], 'limitations': []})
    with patch.object(vision, 'call_model', AsyncMock(return_value=body)), \
         patch.object(vision.asyncio, 'wait_for', recording_wait_for):
        result = asyncio.run(vision.find_proposals(raw, inspect_image(raw, 'p.png', 'image/png'), 'owner'))
    assert result['available']
    model_limit = limits[-1]  # the first wait is for a free slot, the last for the model
    assert 59 < model_limit <= 60
