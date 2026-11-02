#!/usr/bin/env bash
# Pull the latest main, reinstall, rebuild and restart ARCE.
# Run as root on the server:  sudo bash /opt/arce/deploy/update.sh
set -euo pipefail

APP=/opt/arce
as_app() { sudo -u arce -H "$@"; }

as_app git -C "$APP" pull --ff-only
as_app "$APP/backend/.venv/bin/python" -m pip install -q -r "$APP/backend/requirements.txt"
as_app bash -c "cd '$APP' && npm ci --no-audit --no-fund && npm run build"

systemctl restart arce-backend

# The first request after a restart loads the OCR models; give it a moment.
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    # As arce: git refuses a repository owned by another user ("dubious ownership").
    echo "ARCE updated to $(as_app git -C "$APP" log -1 --format='%h %s')"
    exit 0
  fi
  sleep 1
done
echo "Backend did not come back - check: journalctl -u arce-backend -n 50" >&2
exit 1
