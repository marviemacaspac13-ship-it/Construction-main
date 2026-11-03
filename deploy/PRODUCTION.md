# ARCE production deployment

**Live at https://arce-app.tech since 3 November 2026.** Installed by following
[HOSTINGER.md](HOSTINGER.md); this file records what that install produced and what is left.
No secrets belong here: the keys live only in the server's `.env` files.

## Where it runs

| | |
| --- | --- |
| Address | https://arce-app.tech (plain `http://` redirects to HTTPS) |
| Server | Hostinger **KVM 1** (1 vCPU, 4 GB RAM, 50 GB NVMe, 2 GB swap), Malaysia, IP `187.124.141.84` |
| OS | Ubuntu 24.04 LTS |
| Code | `/opt/arce`, a clone of `main` from GitHub, owned by the `arce` user |
| Backend | systemd service `arce-backend` (one uvicorn worker on `127.0.0.1:8000`), Python 3.13 venv at `/opt/arce/backend/.venv` |
| Frontend | built into `/opt/arce/dist`, served by nginx 1.24 |
| Web server | nginx site `/etc/nginx/sites-available/arce` (from [nginx-arce.conf](nginx-arce.conf)) |
| HTTPS | Let's Encrypt for `arce-app.tech`, auto-renewing (first expiry 1 Feb 2027) |
| Firewall | `ufw`: SSH and Nginx Full (80/443) only |
| Database | the same Supabase project as development; Site URL set to https://arce-app.tech |

## Settings that matter

- **Gemini is on** for both plumbing and electrical (`PLUMBING_VISION_ENABLED`,
  `ELECTRICAL_VISION_ENABLED`): the client accepts that drawings are sent to Google. Electrical
  uses `gemini-3.6-flash` with one overload retry, then local symbol matching; plumbing tries
  3.6, 3.8, 3.7, 2.5 Flash and the Flash-Lites, then the label reader. Free tier, so overloads
  happen; they slow a scan down but never break it.
- **The server has its own signing secrets** (`ESTIMATE_INPUT_SECRET`, `PLUMBING_REVIEW_SECRET`,
  `ELECTRICAL_REVIEW_SECRET`), generated on the server, so a backend restart does not force a
  rescan.
- **`VITE_SCAN_API_URL=https://arce-app.tech`** in `/opt/arce/.env.production.local`. It is baked
  into the build: change it and rebuild.

## Checked on the live site, 3 November 2026

| Test | Result | Time |
| --- | --- | --- |
| Floor plan `01` PNG | ₱309,364.97, same as development | 7.5 s |
| Same plan as a one-page PDF | ₱309,364.97, converted in the browser | 6.5 s |
| Plumbing restroom `02` | 11 WC, 12 LAV, 4 U, exact; ₱31,867 | ~46 s |
| Electrical `05` | 47 devices reviewed; ₱22,487.16 partial | ~50 s |
| Reopen a saved project | total and original plan image load | - |
| A broken upload | refused: "corrupt or unsupported" | - |

Also confirmed: `/health` answers, page routes survive a refresh, the pdf.js worker is served as
JavaScript, and `http://` redirects to `https://`.

## What the install hit (all now fixed in HOSTINGER.md)

1. **Backend would not start:** `libGL.so.1: cannot open shared object file`. The OCR engine pulls
   in the full `opencv-python` as well as the headless one. Fix: `apt install libgl1 libglib2.0-0t64`.
2. **Site returned 500:** nginx could not enter `/opt/arce` (`adduser` makes it 750). Fix:
   `chmod 711 /opt/arce`; the `.env` files stay 600.
3. **Scans crashed to a blank page over plain http:** `crypto.randomUUID is not a function`,
   which browsers only provide on HTTPS or localhost. Fix: HTTPS, which is now marked mandatory.

## Still open

- [ ] **Switch off SSH password login** (HOSTINGER.md, Phase 3). Key login works.
- [ ] **`www.arce-app.tech`**: no DNS record yet, so the certificate covers the bare domain only.
      To add it: an A record for `www` to the server IP, then
      `certbot --nginx -d arce-app.tech -d www.arce-app.tech`.
- [ ] **Backups**: turn on Hostinger VPS snapshots if the plan includes them. The server holds the
      estimate log (`backend/runs/`) and any Symbol Library uploads; projects live in Supabase.
- [ ] **Separate Supabase project for real clients** (optional): production and development share
      one database today, test projects included.
- [ ] **2+ vCPU** before wider use; fine for a demo or a few users now.

## Everyday operation

| Task | On the server |
| --- | --- |
| Deploy a new version (after `git push`) | `sudo bash /opt/arce/deploy/update.sh` |
| Backend log | `journalctl -u arce-backend -n 50` (add `-f` to follow) |
| Restart the backend | `systemctl restart arce-backend` (also after editing `materials`) |
| nginx errors | `tail -f /var/log/nginx/error.log` |
| Certificate renewal check | `certbot renew --dry-run` |

`update.sh` rebuilds the frontend, which empties `/opt/arce/dist`; never keep anything there by
hand. Rolling back is described in HOSTINGER.md, section 3.
