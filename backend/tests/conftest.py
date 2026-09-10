import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def catalog() -> dict[str, dict]:
    """The 52-SKU catalog snapshot, keyed by item_id - same shape load_catalog() returns."""
    rows = json.loads((FIXTURES / "catalog.json").read_text(encoding="utf-8"))
    return {row["item_id"]: row for row in rows}
