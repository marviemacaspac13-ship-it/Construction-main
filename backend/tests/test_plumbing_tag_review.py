"""Offline evidence must preserve route decisions and include refused reads."""
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from app.extract.ocr import TextBox
from scripts.review_plumbing_tags import capture, pixel_hash
from scripts.probe_tag_duplicates import deduplicate


@pytest.mark.parametrize("number,status", [(0, "refused"), (1, "refused"), (3, "accepted")])
def test_review_keeps_counts_and_refusal(number, status):
    image = np.full((200, 200, 3), 255, np.uint8)
    raw = cv2.imencode(".png", image)[1].tobytes()
    boxes = [TextBox("WC", 20 + 40 * i, 50, .9, False) for i in range(number)]
    with patch("scripts.review_plumbing_tags.read_tiled", return_value=boxes):
        result = capture(raw, image)
    assert result["status"] == status
    assert result["before_counts"] == result["after_counts"]
    assert len(result["observations"]) == number
    assert all(o["review"] == "unreviewed" for o in result["observations"])


def test_cleanouts_are_captured_but_do_not_pass_material_floor():
    image = np.full((200, 200, 3), 255, np.uint8)
    raw = cv2.imencode(".png", image)[1].tobytes()
    boxes = [TextBox("CO", 20 + 40 * i, 50, .9, False) for i in range(4)]
    with patch("scripts.review_plumbing_tags.read_tiled", return_value=boxes):
        result = capture(raw, image)
    assert result["status"] == "refused"
    assert result["after_counts"] == {"cleanout": 4}


def test_content_hash_uses_shape_and_pixels_not_encoding():
    image = np.full((20, 30, 3), 255, np.uint8)
    encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1]
    assert pixel_hash(image) == pixel_hash(cv2.imdecode(encoded, cv2.IMREAD_COLOR))
    assert pixel_hash(image) != pixel_hash(image.reshape(30, 20, 3))
    changed = image.copy()
    changed[0, 0] = 0
    assert pixel_hash(image) != pixel_hash(changed)


def test_candidate_merges_variants_but_keeps_other_classes_and_distant_tags():
    observations = [
        dict(id="a", tag="water_closet", text="WC", cx=10, cy=20, score=.8),
        dict(id="b", tag="water_closet", text="wC", cx=11, cy=21, score=.9),
        dict(id="c", tag="floor_drain", text="FD", cx=11, cy=21, score=.9),
        dict(id="d", tag="water_closet", text="WC", cx=10, cy=60, score=.9),
    ]
    kept, removed = deduplicate(observations)
    assert {o["id"] for o in kept} == {"b", "c", "d"}
    assert removed == [dict(id="a", retained_id="b", tag="water_closet", dx=1, dy=1)]
