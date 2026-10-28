"""Routes that read an image must run on a worker thread, not the event loop.

FastAPI runs an `async def` route on its single event loop. A floor-plan OCR
pass takes 10-60 s, so an `async` route doing it inline froze every other
request for that long - including other users' saves and the Gemini calls
whose timeouts are measured on that same loop. A plain `def` route runs in
FastAPI's thread pool instead.
"""
import inspect

import pytest

from app import main


@pytest.mark.parametrize("route", [main.estimate_image, main.scan_plan, main.upload_template])
def test_image_heavy_routes_are_not_coroutines(route):
    assert not inspect.iscoroutinefunction(route), route.__name__
