"""Drain abandoned/deleted-project file queues. Run periodically after migration 005.

From backend/: .venv/Scripts/python.exe scripts/cleanup_plan_files.py
Ready originals, including failed scans and historical versions, are never expired.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from app.plan_assets import cleanup_plans, require_plan_storage
from app.revisions import rpc


def main():
    require_plan_storage()
    owners = rpc('plan_cleanup_owners', {})
    removed = 0
    failed = 0
    for owner in owners:
        try:
            removed += cleanup_plans(owner)['removed']
        except Exception:
            # No paths, user IDs, signed URLs or credentials in maintenance output.
            failed += 1
    print(f'Removed {removed} queued plan files; {failed} owner queues need retry.')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
