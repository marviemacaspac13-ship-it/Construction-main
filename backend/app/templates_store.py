import re
import uuid
from pathlib import Path
import cv2
import numpy as np

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Names arriving from a request must never be able to address a file outside
# TEMPLATES_DIR. Two independent guards, both here in the store so they
# protect every caller rather than one route: a whitelist on each name, and
# a containment check on the resolved path.
#
# A whitelist rather than a blacklist of "..", "/" and "\": on Windows a
# name like "C:x" changes drive when joined, with no dot or slash in it.
_ITEM_ID = re.compile(r"[A-Za-z0-9_-]{1,32}")          # CLR01, OT01, CHB02
_FILENAME = re.compile(r"[A-Za-z0-9_-]{1,64}\.[A-Za-z0-9]{1,8}")
_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,8}")


class UnsafeTemplatePath(ValueError):
    """A template name that is not a plain, single path segment."""


def _safe_path(item_id: str, filename: str | None = None) -> Path:
    if not _ITEM_ID.fullmatch(item_id or ""):
        raise UnsafeTemplatePath("invalid item id")
    if filename is not None and not _FILENAME.fullmatch(filename):
        raise UnsafeTemplatePath("invalid template filename")

    root = TEMPLATES_DIR.resolve()
    path = root / item_id if filename is None else root / item_id / filename
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise UnsafeTemplatePath("path escapes the template directory")
    return resolved


def save_template(item_id: str, raw_bytes: bytes, original_filename: str) -> str:
    item_dir = _safe_path(item_id)
    item_dir.mkdir(parents=True, exist_ok=True)

    # The stored name is generated, never taken from the upload; only the
    # extension survives, and only if it is a plain one.
    ext = Path(original_filename).suffix
    if not _EXTENSION.fullmatch(ext):
        ext = ".png"
    filename = f"{uuid.uuid4().hex}{ext.lower()}"
    (item_dir / filename).write_bytes(raw_bytes)
    return filename


def delete_template(item_id: str, filename: str) -> bool:
    """Delete one reference crop. Raises UnsafeTemplatePath on a bad name."""
    path = _safe_path(item_id, filename)
    if path.is_file():
        path.unlink()
        return True
    return False


def list_templates() -> dict[str, list[str]]:
    if not TEMPLATES_DIR.exists():
        return {}
    result: dict[str, list[str]] = {}
    for item_dir in sorted(TEMPLATES_DIR.iterdir()):
        if item_dir.is_dir():
            files = sorted(f.name for f in item_dir.iterdir() if f.is_file())
            if files:
                result[item_dir.name] = files
    return result


def load_templates_for_matching() -> list[tuple[str, np.ndarray]]:
    templates: list[tuple[str, np.ndarray]] = []
    for item_id, filenames in list_templates().items():
        for filename in filenames:
            path = TEMPLATES_DIR / item_id / filename
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                templates.append((item_id, img))
    return templates
