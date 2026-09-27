"""Count the structural columns a floor plan draws.

A CAD floor plan draws each column as a small solid black square at a wall
junction. Counting them replaces the one layout guess the frame otherwise
makes - a column every `column_spacing_m` round the envelope - with what
the draughtsman put on the sheet, interior columns included.

A count needs no scale. That matters: the ruler in `scale.py` is confirmed
on only two plans of four, and a count sidesteps it entirely. Only the
NUMBER of columns comes from here; their section stays the Guide.docx
constant (`test_frame_against_drawings.py` pins why).

Method, from docs/measurement-plan.md Phase 5: threshold the dark pixels,
open with a kernel wider than any wall line so lines vanish and solid
blocks survive, then keep components that are column-sized, roughly
square, and nearly solid. On the two CAD plans it finds 16 of 16 and 10 of
10 with no false hits. Hand sketches and scans draw no solid squares and
find next to nothing, which `frame.plausible_column_count` turns into a
fallback.
"""

import cv2
import numpy as np

DARK = 100
# Opening with this kernel erases anything thinner than it - dimension
# lines, furniture outlines, text strokes - and keeps solid blocks. Walls on
# the CAD sheets are drawn grey, lighter than DARK, so they never enter.
# Columns are about 20-30 px across.
OPEN_KERNEL = 5
MIN_SIDE_PX = 10
MAX_SIDE_PX = 40
MIN_ASPECT, MAX_ASPECT = 0.6, 1.6
MIN_FILL = 0.80


def count_drawn_columns(image: np.ndarray) -> int:
    """Solid, column-sized squares on the sheet."""
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dark = (gray < DARK).astype(np.uint8)
    kernel = np.ones((OPEN_KERNEL, OPEN_KERNEL), np.uint8)
    solid = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
    n, _, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
    found = 0
    for i in range(1, n):
        _, _, w, h, area = stats[i]
        if not (MIN_SIDE_PX <= w <= MAX_SIDE_PX and MIN_SIDE_PX <= h <= MAX_SIDE_PX):
            continue
        if not MIN_ASPECT <= w / h <= MAX_ASPECT:
            continue
        if area / float(w * h) < MIN_FILL:
            continue
        found += 1
    return found

