import uuid
from pathlib import Path
import cv2
import numpy as np

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def save_template(item_id: str, raw_bytes: bytes, original_filename: str) -> str:
    item_dir = TEMPLATES_DIR / item_id
    item_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(original_filename).suffix or ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    (item_dir / filename).write_bytes(raw_bytes)
    return filename


def delete_template(item_id: str, filename: str) -> bool:
    path = TEMPLATES_DIR / item_id / filename
    if path.exists():
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
