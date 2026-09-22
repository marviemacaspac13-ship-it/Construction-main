"""Refining a detection's label from the text printed beside it.

A drawing puts the same circle on a general-purpose outlet and on an
air-conditioning outlet. What separates them is the word written next to
it, and the matcher cannot see a word - it compares shapes - so an ACU has
always been counted, and priced, as an ordinary outlet.

**Only a whitelist may rename a detection, and that is the whole safety
argument.** Measured on `05.png`: `ACU` sits 32 px from its outlet, but
`BEDROOM1` sits 40 px from a ceiling outlet and `TOILET & BATH` 23 px from
another. A nearest-text-wins rule would relabel a ceiling receptacle
"TOILET & BATH". Text that is not in `RELABEL` is ignored, always, and a
rename is refused unless the detection already carries a label the rename
is declared to apply to - so `ACU` can turn a wall outlet into an AC
outlet and can never touch a ceiling receptacle.

What this deliberately does NOT do, because the drawing does not say it:

* **Gang counts.** `OT01`/`OT02`/`OT03` share one circle and the legend
  distinguishes them, but the plan does not annotate which is which. Every
  text box within 40 px of all 28 detections on `05.png` was dumped: room
  labels, no digits. The 1-gang assumption stays an assumption.
* **Switches.** `S`, `S2`, `S3w` are marks about ten pixels tall and are
  not adjacent to any detection - they are their own symbols. Three
  independent routes have now failed on them: a whole-page read finds 0 of
  ~10, a tiled read finds 1, and template-matching the glyph gives no
  clean threshold. Do not try a fourth.
"""

import math

from app.extract.ocr import TextBox
from app.extract.tags import normalise_tag
from app.schemas import Detection

# How far a word may sit from a symbol and still describe it, as a fraction
# of the longer image side. Never a pixel count: these sheets run from
# 0.16 MP to 3.15 MP. 0.06 of 641 px is ~38 px, and the one real example in
# the corpus sits at 32.
ADJACENT_MAX_FRAC = 0.06

# text -> (label it becomes, labels it is allowed to rename)
#
# Keep both halves tight. The first stops unknown words renaming anything;
# the second stops a known word renaming the wrong kind of symbol.
RELABEL: dict[str, tuple[str, frozenset[str]]] = {
    "ACU": ("ACO01", frozenset({"OT01"})),
    "AC": ("ACO01", frozenset({"OT01"})),
}


def _centre(detection: Detection) -> tuple[float, float]:
    x1, y1, x2, y2 = detection.bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


def relabel_from_adjacent_text(
    detections: list[Detection],
    boxes: list[TextBox],
    image_shape: tuple[int, ...],
) -> list[Detection]:
    """Rename detections that have a whitelisted word beside them.

    Returns a new list; the input is not modified. A detection with no
    qualifying word keeps the label the matcher gave it, which is the
    common case - one of 28 detections on `05.png` is renamed.

    Each word claims at most one detection and each detection is claimed at
    most once, nearest first, so a single `ACU` cannot convert a cluster of
    outlets into a row of air-conditioning points.
    """
    if not detections or not boxes or len(image_shape) < 2:
        return list(detections)

    height, width = image_shape[0], image_shape[1]
    limit = max(height, width) * ADJACENT_MAX_FRAC

    # Every (word, detection) pair close enough to be a description, nearest
    # first, so the closest reading wins a contested symbol.
    pairs: list[tuple[float, int, int, str]] = []
    for b_index, box in enumerate(boxes):
        text = normalise_tag(box.text)
        rename = RELABEL.get(text)
        if rename is None:
            continue
        new_label, applies_to = rename
        for d_index, detection in enumerate(detections):
            if detection.label not in applies_to:
                continue
            distance = math.dist(_centre(detection), (box.cx, box.cy))
            if distance <= limit:
                pairs.append((distance, b_index, d_index, new_label))

    pairs.sort(key=lambda p: p[0])

    claimed_boxes: set[int] = set()
    claimed_detections: set[int] = set()
    renames: dict[int, str] = {}
    for _, b_index, d_index, new_label in pairs:
        if b_index in claimed_boxes or d_index in claimed_detections:
            continue
        claimed_boxes.add(b_index)
        claimed_detections.add(d_index)
        renames[d_index] = new_label

    return [
        d.model_copy(update={"label": renames[i]}) if i in renames else d
        for i, d in enumerate(detections)
    ]
