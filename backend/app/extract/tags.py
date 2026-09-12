"""Counting printed tags - fixtures, devices - by reading them off the page.

Some things on a plan are drawn and some are written. `WC`, `LAV`, `FD`
next to a plumbing fixture are text, not glyphs, so template matching
cannot reach them; and a whole-page OCR pass cannot either, because the
detector proposes different regions on a small image than on a busy one.
On `07.png` the full page finds 0 of about 13 water closets.

The fix is the Task 18 trick applied to the whole sheet rather than to one
label: re-read it in overlapping tiles. Tiles recover the tags, and
`merge_boxes` deduplicates by text AND position, which is what makes the
result a COUNT rather than a pile of hits - without it the overlaps report
`LAV` 39 times against about 11 real ones.

What this is not: accurate. There is no checksum on a tag count the way a
dimension chain checks itself, and a missed fixture is invisible. Treat the
numbers as a reading, report them as such, and see `docs/TODO.md` for the
open question of what could ever validate one.
"""

import re
from collections import Counter
from dataclasses import dataclass

import numpy as np

from app.extract.ocr import TextBox, merge_boxes, read_array, read_region

# A 5x5 sweep recovers the most on the sample plumbing plan without the
# runtime running away: each tile is a separate pair of OCR calls.
TILE_GRID = 5

# Tiles overlap so a tag sitting on a boundary is not cut in half. Wider
# than the largest tag by a good margin.
TILE_OVERLAP_PX = 20

# Leading and trailing marks OCR picks up from the leader line next to a
# tag: "+ FD", "FD *", "-ED" all mean FD.
_EDGE_NOISE = ".,*+-:;_ "


def normalise_tag(text: str) -> str:
    return text.upper().strip(_EDGE_NOISE)


@dataclass(frozen=True)
class TagCount:
    """How many of one tag were read, and how sure that is."""

    tag: str
    count: int
    # Boxes the count came from, so a caller can show or check them.
    boxes: tuple[TextBox, ...] = ()


def read_tiled(
    image: np.ndarray, grid: int = TILE_GRID, overlap: int = TILE_OVERLAP_PX
) -> list[TextBox]:
    """Whole-page read plus an overlapping tile sweep, merged and deduped."""
    height, width = image.shape[:2]
    tile_h, tile_w = height // grid, width // grid
    if tile_h < 2 or tile_w < 2:
        return read_array(image)

    found: list[TextBox] = []
    for row in range(grid):
        for col in range(grid):
            y1 = max(0, row * tile_h - overlap)
            y2 = min(height, (row + 1) * tile_h + overlap)
            x1 = max(0, col * tile_w - overlap)
            x2 = min(width, (col + 1) * tile_w + overlap)
            found += read_region(image, x1, y1, x2, y2)

    return merge_boxes(read_array(image), found)


def count_tags(boxes: list[TextBox], patterns: dict[str, str]) -> dict[str, TagCount]:
    """Count boxes whose text matches each named pattern.

    `patterns` maps a tag name to a regex matched against the normalised
    box text. Every tag asked for comes back, at zero if unseen - a caller
    needs to tell "none on this plan" apart from "not looked for".
    """
    compiled = {tag: re.compile(p, re.I) for tag, p in patterns.items()}
    hits: dict[str, list[TextBox]] = {tag: [] for tag in patterns}

    for box in boxes:
        text = normalise_tag(box.text)
        if not text:
            continue
        for tag, pattern in compiled.items():
            if pattern.fullmatch(text):
                hits[tag].append(box)
                break  # a tag belongs to one kind

    return {
        tag: TagCount(tag=tag, count=len(found), boxes=tuple(found))
        for tag, found in hits.items()
    }


def tally(counts: dict[str, TagCount]) -> Counter:
    """Just the numbers, for logging and comparison."""
    return Counter({tag: tc.count for tag, tc in counts.items() if tc.count})
