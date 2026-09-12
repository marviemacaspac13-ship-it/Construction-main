"""Parsing of the text a floor plan carries.

Two token kinds matter for a takeoff:
  - room labels with dimensions, e.g. "KITCHEN 3700 x 4000"
  - bare dimension values in the margin chains, e.g. "3200", "134.5"

Everything here is pure text -> numbers. Getting the text off the image is
the OCR layer's job (see ocr.py); this module is what validates it.
"""

import re
from dataclasses import dataclass

# "3700 x 4000", "294X294", "312 X 444", "3.7x4.0"
ROOM_DIM_RE = re.compile(
    r"(?P<w>\d+(?:\.\d+)?)\s*[xX\u00d7]\s*(?P<l>\d+(?:\.\d+)?)"
)

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# Door/window schedule tags: W1, W3, D1, D2, V, plus bare D
DOOR_TAG_RE = re.compile(r"^D\d*$", re.IGNORECASE)
WINDOW_TAG_RE = re.compile(r"^W\d*$", re.IGNORECASE)


@dataclass(frozen=True)
class RoomToken:
    """A room label and its printed dimensions, in the drawing's own units."""

    name: str
    width: float
    length: float

    @property
    def area(self) -> float:
        return self.width * self.length

    @property
    def perimeter(self) -> float:
        return 2.0 * (self.width + self.length)


def parse_room(text: str) -> RoomToken | None:
    """Parse a room block such as "KITCHEN\n3700 x 4000".

    Returns None when the text carries no dimension pair.
    """
    match = ROOM_DIM_RE.search(text)
    if match is None:
        return None
    name = text[: match.start()].strip().strip("-\u2013:").strip()
    name = " ".join(name.split())
    return RoomToken(
        name=name,
        width=float(match.group("w")),
        length=float(match.group("l")),
    )


# A room is never this much longer than it is wide. The worst in the sample
# corpus is a toilet at 2.85, so 6.0 leaves room for a long corridor while
# still rejecting title-block text: "SCALE: 10 : 1 MTS" parses as 10 x 1,
# because the separator repair turns any punctuation between two digits
# into the dimension "x".
MAX_ROOM_ASPECT = 6.0


def is_plausible_room(room: RoomToken) -> bool:
    if room.width <= 0 or room.length <= 0:
        return False
    return max(room.width, room.length) / min(room.width, room.length) <= MAX_ROOM_ASPECT


def parse_rooms(blocks: list[str]) -> list[RoomToken]:
    """Parse many room blocks, skipping any that carry no usable dimensions."""
    out = []
    for block in blocks:
        room = parse_room(block)
        if room is not None and is_plausible_room(room):
            out.append(room)
    return out


def parse_numbers(text: str) -> list[float]:
    """Every numeric value in a margin dimension chain, in reading order."""
    return [float(m.group(0)) for m in NUMBER_RE.finditer(text)]


def classify_tag(tag: str) -> str | None:
    """D1 -> door, W3 -> window, anything else -> None."""
    tag = tag.strip()
    if DOOR_TAG_RE.match(tag):
        return "door"
    if WINDOW_TAG_RE.match(tag):
        return "window"
    return None


def count_openings(tags: list[str]) -> dict[str, int]:
    """Count door and window schedule tags. Unknown tags are ignored."""
    counts = {"door": 0, "window": 0}
    for tag in tags:
        kind = classify_tag(tag)
        if kind is not None:
            counts[kind] += 1
    return counts
