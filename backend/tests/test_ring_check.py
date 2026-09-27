"""The ring check in app/vision/template_match.py.

Every symbol in the library is drawn on a circle; a bare crossing of two
thin lines is not, but it is most of a crossed-circle template and scored
0.66-0.70 against it. On 27 Sep 2026 that was 10 of 08.png's 17 "lights"
and all 4 on the power-only 10.png. The check keeps a hit only if ink
surrounds its centre in the off-axis directions.

The check runs on the PLAN, never on a library crop, so there is no test
here that the crops pass it: a legend symbol shrunk to 20 px renders its
circle light grey and scores low on itself, while the dark circle it
matches on a drawing passes. The guard that matters is that real symbols
on real sheets survive - tests/test_ground_truth.py, where 08.png must keep
all 19 of its lights.
"""

import cv2
import numpy as np

from app.vision.template_match import RING_MIN, ring_score


def blank(size=60):
    return np.full((size, size), 255, np.uint8)


def test_a_circle_passes():
    img = blank()
    cv2.circle(img, (30, 30), 7, 0, 1)
    assert ring_score(img, [20, 20, 40, 40]) >= RING_MIN


def test_a_crossed_circle_passes():
    img = blank()
    cv2.circle(img, (30, 30), 7, 0, 1)
    cv2.line(img, (20, 30), (40, 30), 0, 1)
    cv2.line(img, (30, 20), (30, 40), 0, 1)
    assert ring_score(img, [20, 20, 40, 40]) >= RING_MIN


def test_a_bare_line_crossing_fails():
    """Exactly the false light: a '+' where two drawing lines meet."""
    img = blank()
    cv2.line(img, (0, 30), (59, 30), 0, 1)
    cv2.line(img, (30, 0), (30, 59), 0, 1)
    assert ring_score(img, [20, 20, 40, 40]) < RING_MIN


def test_a_box_near_the_image_edge_does_not_crash():
    assert ring_score(blank(), [-5, -5, 10, 10]) == 0.0
