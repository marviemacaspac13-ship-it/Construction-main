import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def catalog() -> dict[str, dict]:
    """The 52-SKU catalog snapshot, keyed by item_id - same shape load_catalog() returns."""
    rows = json.loads((FIXTURES / "catalog.json").read_text(encoding="utf-8"))
    return {row["item_id"]: row for row in rows}


@pytest.fixture(autouse=True)
def signed_in(request):
    """Every test calls the API as a signed-in user unless it says otherwise.

    The real check asks Supabase over the network (app/auth.py), which the
    offline suite cannot do. Tests of that check itself are marked
    `real_auth` and get the real dependency.
    """
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    from app.auth import current_user
    from app.main import app

    app.dependency_overrides[current_user] = lambda: "test-user"
    yield
    app.dependency_overrides.pop(current_user, None)
