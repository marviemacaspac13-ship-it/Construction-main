import os
from functools import lru_cache
from supabase import create_client, Client


def _client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set — check your .env file.")
    return create_client(url, key)


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict]:
    data = _client().table("materials").select("item_id, item_name, unit, price, category").execute()
    return {row["item_id"]: row for row in data.data}
