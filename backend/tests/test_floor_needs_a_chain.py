"""A floor plan with no dimension chain read is refused, never priced (R28).

A chain is what lets the drawing check itself: its segments must add up to the
printed overall. With none, the building outline comes from numbers nothing
can check. Shrinking the four sample plans showed what that costs - every read
with no chain priced the building at 1.6x to 2.7x its full-size total:

    01.png at 30%   P493,909 against P309,365   no chain
    02.jpg at 50%   P573,945 against P245,280   no chain
    03.png at 30%   P608,390 against P225,220   no chain

while every read within 5% of full size had at least one chain. Confidence
does not separate them (a 24%-wrong read scored 0.71, a correct one 0.47),
and nor does printed-digit height in pixels.

Not covered: a read that HAS a chain can still be wrong - 02.jpg at 70% was
24% over, 04.jpg at 50% 12% under. A rooms-cover-the-outline floor would
catch those but rests on four plans; it waits for real client plans.
"""
import io
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.extract.to_plan import extract_plan
from app.main import app
from tests.fixtures.sample_plans import CAD_WIDE

client = TestClient(app)
PLANS = Path(__file__).parent / "fixtures" / "plans"


def png(image=None):
    buffer = io.BytesIO()
    (image or Image.new("RGB", (120, 80), "white")).save(buffer, format="PNG")
    return buffer.getvalue()


def extraction(chains):
    """A hand-transcribed sample plan, read with or without its margin chains."""
    return extract_plan(CAD_WIDE.envelope_w, CAD_WIDE.envelope_l, CAD_WIDE.room_blocks, chains)


def estimate(raw):
    return client.post("/api/estimate/image", files={"file": ("plan.png", raw, "image/png")},
                       data={"plan_type": "Floor Plan"})


def test_no_dimension_chain_is_refused_with_guidance():
    with patch("app.main.read_plan_bytes", return_value=extraction(None)):
        result = estimate(png())
    assert result.status_code == 422
    message = result.json()["detail"]["message"]
    assert "dimension" in message
    assert "original export" in message


def test_one_chain_is_enough_to_pass_this_guard(catalog):
    with patch("app.main.read_plan_bytes", return_value=extraction(CAD_WIDE.chains[:1])), \
         patch("app.main.load_catalog", return_value=catalog):
        result = estimate(png())
    assert result.status_code == 200, result.text


def shrunk(name, scale):
    image = Image.open(PLANS / name).convert("RGB")
    return png(image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS))


@pytest.mark.ocr
@pytest.mark.parametrize("name,scale", [("01.png", .3), ("03.png", .3), ("02.jpg", .5)])
def test_shrunk_sample_plans_with_no_chain_are_refused(name, scale):
    assert estimate(shrunk(name, scale)).status_code == 422


@pytest.mark.ocr
@pytest.mark.parametrize("name,scale", [("01.png", .4), ("03.png", .5)])
def test_shrunk_sample_plans_that_still_read_are_still_priced(name, scale):
    assert estimate(shrunk(name, scale)).status_code == 200
