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


# A legend row sits its expansion just to the right of the tag, on the same
# line. Both windows are fractions of the image rather than pixel counts:
# a flat number is right at one scale and wrong at every other, which is
# the mistake the chain tolerances made before Task 20.
LEGEND_MAX_DX_FRAC = 0.15
LEGEND_ROW_TOL_FRAC = 0.015

# ...and a MINIMUM gap, because the two OCR passes read the same glyph
# slightly differently - 'WC' and "wC'" land at the same coordinates, 'FD'
# and 'FQ*' one pixel apart. merge_boxes keeps both, the strings differing,
# and without this floor the longer misread looks like an expansion of the
# shorter one. That cost three real fixtures on the sample sanitary plan,
# which is a worse bug than the legend it was meant to fix. On the sample
# legend the real gap is 7.4% of the width, so 2% clears the duplicates
# with room to spare.
LEGEND_MIN_DX_FRAC = 0.02


def _is_legend_row(
    tag_box: TextBox,
    boxes: list[TextBox],
    min_dx: float,
    max_dx: float,
    row_tol: float,
) -> bool:
    """True when this tag is a legend entry rather than a fixture on the plan.

    A legend reads `LAV  LAVATORY`: the tag, then its expansion immediately
    to the right on the same line, and the expansion begins with the same
    letter. That last part is what makes this safe - on the sample legend
    all nine rows match it, while a fixture label that happens to sit near
    other text almost never will.

    Counting a legend costs a phantom fixture per row, and on a plan whose
    fixtures are too faint to read but whose legend is crisp, EVERY count
    would come from the legend.
    """
    tag_text = normalise_tag(tag_box.text)
    if not tag_text:
        return False

    for other in boxes:
        if other is tag_box:
            continue
        text = other.text.strip()
        if len(text) <= len(tag_text):
            continue
        if abs(other.cy - tag_box.cy) > row_tol:
            continue
        if not min_dx <= other.cx - tag_box.cx <= max_dx:
            continue
        if text[:1].upper() == tag_text[:1].upper():
            return True
    return False


def count_tags(
    boxes: list[TextBox],
    patterns: dict[str, str],
    image_shape: tuple[int, ...] | None = None,
) -> dict[str, TagCount]:
    """Count boxes whose text matches each named pattern.

    `patterns` maps a tag name to a regex matched against the normalised
    box text. Every tag asked for comes back, at zero if unseen - a caller
    needs to tell "none on this plan" apart from "not looked for".

    Pass `image_shape` to suppress legend rows. Without it the windows have
    no scale to be relative to, so legend suppression is skipped rather
    than guessed at, and a plan carrying a legend will over-count.
    """
    compiled = {tag: re.compile(p, re.I) for tag, p in patterns.items()}
    hits: dict[str, list[TextBox]] = {tag: [] for tag in patterns}

    min_dx = max_dx = row_tol = 0.0
    if image_shape is not None:
        height, width = image_shape[0], image_shape[1]
        min_dx = width * LEGEND_MIN_DX_FRAC
        max_dx = width * LEGEND_MAX_DX_FRAC
        row_tol = height * LEGEND_ROW_TOL_FRAC

    for box in boxes:
        text = normalise_tag(box.text)
        if not text:
            continue
        for tag, pattern in compiled.items():
            if pattern.fullmatch(text):
                if max_dx and _is_legend_row(box, boxes, min_dx, max_dx, row_tol):
                    break
                hits[tag].append(box)
                break  # a tag belongs to one kind

    return {
        tag: TagCount(tag=tag, count=len(found), boxes=tuple(found))
        for tag, found in hits.items()
    }


def tally(counts: dict[str, TagCount]) -> Counter:
    """Just the numbers, for logging and comparison."""
    return Counter({tag: tc.count for tag, tc in counts.items() if tc.count})
