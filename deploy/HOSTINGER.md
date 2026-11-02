# Deploying ARCE on a Hostinger VPS

A plan and step-by-step guide for putting ARCE online on a Hostinger KVM VPS
(written for **KVM 1**: 1 vCPU, 4 GB RAM, 50 GB NVMe). Budget one to two hours the first time.

Placeholders used throughout. Replace them with your own:

| Placeholder | Meaning |
| --- | --- |
| `arce.example.com` | the domain or subdomain the app will live on |
| `203.0.113.10` | your VPS's public IP address (shown in hPanel) |
| `you@example.com` | the email Let's Encrypt sends certificate notices to |

The files this guide installs live next to it in `deploy/`:
[nginx-arce.conf](nginx-arce.conf), [arce-backend.service](arce-backend.service),
[update.sh](update.sh).

---

## 1. The plan

### What runs where

```
 browser ──HTTPS──▶ nginx on the VPS ──┬─▶ /opt/arce/dist         (the built React app)
                                       └─▶ /api/*, /health ──▶ uvicorn 127.0.0.1:8000 (FastAPI)

 browser ─────────▶ Supabase (sign-in, projects, saved estimates)   ◀── stays where it is
 FastAPI ─────────▶ Supabase (materials catalog, plan storage)
 FastAPI ─────────▶ Google Gemini (only if the vision flags are on)
```

- **Supabase is not moved.** It is already hosted; the VPS only runs the frontend and the
  Python backend. There is no database on the server.
- **One domain for both halves.** nginx serves the app and passes `/api/*` to the backend, so
  the browser never makes a cross-origin call. That means the localhost-only CORS list in
  `backend/app/main.py` does not need editing, and **no application code changes are
  needed to deploy**. Every backend route is under `/api/` except `/health`.
- **Nothing to back up on the server except two folders** (section 6): the symbol library
  (`backend/templates/`) and the estimate ledger (`backend/runs/`). Everything else is
  rebuilt from git.

### Decisions to make first

| Decision | Options | Recommendation |
| --- | --- | --- |
| **Domain** | a new domain, or a subdomain of one you own | A subdomain (e.g. `arce.yourcompany.com`) is free if you already have a domain. Buying it at Hostinger makes the DNS step simplest. |
| **Gemini** | on (better electrical/plumbing proposals) or off (scans stay on your server) | With it on, **every client's electrical or plumbing drawing is uploaded to Google.** Decide this deliberately. Turn it off until clients have agreed, or tell them on the upload screen. |
| **Supabase project** | reuse the current one, or create a separate production project | Reusing it is fine for a demo, but test projects and real client projects will share one database. Use a separate project once real clients sign up (it needs migrations 001-006 run and the `materials` table copied). |
| **Server size** | KVM 1 (1 vCPU) or a 2+ vCPU plan | See below. |

### What KVM 1 can and cannot do

These numbers were measured on 2 Nov 2026 by running the real readers held to a single CPU
core. A VPS core may be slower, so treat them as best case:

| Scan (Gemini off) | 1 core | 12 cores | Peak memory |
| --- | --- | --- | --- |
| Floor plan (`01`) | 15 s | 2.3 s | ~390 MB |
| Plumbing labels (`03`) | **106 s** | 16 s | ~340 MB |

- Memory, disk and bandwidth are more than enough.
- **Plumbing scans take about two minutes**, with Gemini on as well: the floor-drain,
  cleanout, hose-bib and drinking-fountain labels are always read locally.
- **Scans queue.** Two people scanning at once roughly double each other's wait.
- Good enough for a demo or a handful of users. Move to 2+ vCPU before wider use.
  The upgrade is done in hPanel and keeps the disk.

### Phases at a glance

| # | Phase | Where |
| --- | --- | --- |
| 0 | Prepare the code and secrets | your PC |
| 1 | Create the VPS | hPanel |
| 2 | Point the domain at it | hPanel (or your DNS provider) |
| 3 | Secure the server | SSH |
| 4 | Install Python 3.13, Node 22, nginx | SSH |
| 5 | Get the code onto the server | SSH |
| 6 | Copy the secrets | your PC → server |
| 7 | Start the backend | SSH |
| 8 | Build the frontend | SSH |
| 9 | nginx and HTTPS | SSH |
| 10 | Supabase settings | Supabase dashboard |
| 11 | Check it works | browser |

---

## 2. Step-by-step guide

### Phase 0 — Prepare (on your PC)

1. **Commit and push everything you want deployed.** The server gets its code from GitHub
   (`origin`), not from your PC. Check with:

   ```powershell
   git status
   git log origin/main..main --oneline   # commits not on GitHub yet
   ```

2. **Make sure no secret is tracked.** These three must print a rule from `.gitignore`:

   ```powershell
   git check-ignore -v backend/.env .env.local passwords.md
   ```

3. **Prepare production secrets.** You will copy `backend/.env` and `.env.local` to the server
   in Phase 6. Before that, open `backend/.env` and decide:
   - `PLUMBING_VISION_ENABLED` / `ELECTRICAL_VISION_ENABLED`: `true` or `false` (the Gemini
     decision above). Note the current file has `PLUMBING_VISION_ENABLED='true'` in quotes,
     which still counts as on.
   - `ESTIMATE_INPUT_SECRET`, `PLUMBING_REVIEW_SECRET`, `ELECTRICAL_REVIEW_SECRET`: give the
     server **new** random values rather than the ones on your PC. Generate them on the server in
     Phase 6. Without them, every backend restart makes people rescan before they can save.

### Phase 1 — Create the VPS (hPanel)

1. Buy the VPS and open it in **hPanel → VPS**. Menu names can shift, but the steps are the same.
2. Choose the operating system **Ubuntu 24.04** in its plain form, *without* a control panel such
   as CloudPanel or Coolify. This guide installs everything itself.
3. Set a strong **root password**, and add your **SSH public key** if hPanel offers it. To make
   a key on Windows, run this in PowerShell and press Enter through the prompts:

   ```powershell
   ssh-keygen -t ed25519
   Get-Content $HOME\.ssh\id_ed25519.pub   # paste this into hPanel
   ```

4. Note the server's **IP address** from the VPS overview.
5. If hPanel shows a **Firewall** for the VPS, allow inbound **22 (SSH), 80 (HTTP) and 443
   (HTTPS)**. The server also gets its own firewall in Phase 3.

### Phase 2 — Point the domain at the server

Create an **A record** for the domain or subdomain pointing at the VPS IP:

| Type | Name | Points to | TTL |
| --- | --- | --- | --- |
| A | `arce` (for `arce.example.com`) or `@` (for the bare domain) | `203.0.113.10` | default |

- Domain at Hostinger: **hPanel → Domains → your domain → DNS / Nameservers → DNS records**.
- Domain elsewhere: add the same record at that registrar.

It can take minutes to a few hours to spread. Check from your PC; it should print the VPS IP:

```powershell
nslookup arce.example.com
```

You can continue with Phases 3-8 while you wait. Phase 9 needs the record working.

### Phase 3 — Secure the server

Connect from PowerShell (Windows 11 has `ssh` built in):

```powershell
ssh root@203.0.113.10
```

Everything from here to Phase 9 runs **on the server**, as root.

```bash
apt update && apt -y upgrade
apt -y install git curl ufw unattended-upgrades

# A user for the app, so it never runs as root
adduser --system --group --home /opt/arce --shell /bin/bash arce

# 2 GB swap as a safety net during npm builds (skip if `swapon --show` already lists some)
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

If you added an SSH key in Phase 1 and `ssh root@…` logged in **without** asking for the
password, switch off password logins:

```bash
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

Do **not** do this if you logged in with the password. You would lock yourself out
(hPanel's browser terminal would still get you in).

### Phase 4 — Install Python 3.13, Node 22 and nginx

The backend's `requirements.txt` is pinned for **Python 3.13** exactly. Ubuntu 24.04 ships
3.12, so it comes from the deadsnakes archive:

```bash
apt -y install software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt -y install python3.13 python3.13-venv python3.13-dev

curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt -y install nodejs nginx certbot python3-certbot-nginx

python3.13 --version   # Python 3.13.x
node --version         # v22.x

ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

### Phase 5 — Get the code

```bash
sudo -u arce -H git clone https://github.com/marviemacaspac13-ship-it/Construction-main.git /opt/arce/app-tmp
sudo -u arce -H bash -c 'shopt -s dotglob && mv /opt/arce/app-tmp/* /opt/arce/ && rmdir /opt/arce/app-tmp'
```

The clone goes to a temporary folder and is moved up because `/opt/arce` already exists as the
user's home.

**If the repository is private,** the clone asks for credentials. Use a read-only **deploy
key** instead of your password:

```bash
sudo -u arce -H mkdir -p -m 700 /opt/arce/.ssh
sudo -u arce -H ssh-keygen -t ed25519 -N '' -f /opt/arce/.ssh/id_ed25519
cat /opt/arce/.ssh/id_ed25519.pub
```

Add that key on GitHub under **repository → Settings → Deploy keys** (leave write access off).
Then clone with the SSH address instead:
`git@github.com:marviemacaspac13-ship-it/Construction-main.git`.

### Phase 6 — Copy the secrets

**On your PC**, from the project folder in PowerShell:

```powershell
scp backend\.env root@203.0.113.10:/opt/arce/backend/.env
scp .env.local   root@203.0.113.10:/opt/arce/.env.local
```

**On the server:**

```bash
cd /opt/arce
# The frontend calls the backend on its own domain (nginx forwards /api).
echo 'VITE_SCAN_API_URL=https://arce.example.com' > .env.production.local

chown arce:arce backend/.env .env.local .env.production.local
chmod 600 backend/.env .env.local

# Fresh signing secrets for production: generate three and paste them into backend/.env
for n in ESTIMATE_INPUT_SECRET PLUMBING_REVIEW_SECRET ELECTRICAL_REVIEW_SECRET; do
  echo "$n=$(openssl rand -hex 32)"
done
nano backend/.env    # replace the three *_SECRET lines; set the two VISION flags as decided
```

`backend/.env` holds the Supabase **service-role** key, which bypasses row-level security.
It must never leave the server or reach git.

### Phase 7 — Start the backend

```bash
sudo -u arce -H python3.13 -m venv /opt/arce/backend/.venv
sudo -u arce -H /opt/arce/backend/.venv/bin/python -m pip install --upgrade pip
sudo -u arce -H /opt/arce/backend/.venv/bin/python -m pip install -r /opt/arce/backend/requirements.txt

cp /opt/arce/deploy/arce-backend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now arce-backend

curl http://127.0.0.1:8000/health      # {"status":"ok"}
journalctl -u arce-backend -n 30       # look for "Application startup complete"
```

Optional sanity check: run the fast test suite. It runs offline and takes a few minutes on one core:

```bash
cd /opt/arce/backend && sudo -u arce -H .venv/bin/python -m pytest -q -m "not ocr"
```

### Phase 8 — Build the frontend

```bash
sudo -u arce -H bash -c 'cd /opt/arce && npm ci --no-audit --no-fund && npm run build'
ls /opt/arce/dist      # index.html and assets/
```

The build reads `.env.local` (Supabase URL and anon key) and `.env.production.local` (the
backend URL). **Change either and you must rebuild.** The values are baked into the files.

### Phase 9 — nginx and HTTPS

```bash
cp /opt/arce/deploy/nginx-arce.conf /etc/nginx/sites-available/arce
sed -i 's/arce.example.com/YOUR.DOMAIN.HERE/' /etc/nginx/sites-available/arce
ln -s /etc/nginx/sites-available/arce /etc/nginx/sites-enabled/arce
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Now `http://arce.example.com` should show the sign-in page. Then add HTTPS. This needs the DNS
record from Phase 2 to resolve, and it asks you to accept Let's Encrypt's terms:

```bash
certbot --nginx -d arce.example.com --redirect -m you@example.com
```

Certbot renews the certificate automatically. Check that renewal works with
`certbot renew --dry-run`.

What the nginx config already handles, and why each part matters:

| Setting | Why |
| --- | --- |
| `client_max_body_size 30m` | nginx refuses uploads over 1 MB by default; plans are up to 25 MB |
| `proxy_read_timeout 300s` | the default 60 s would cut off a two-minute plumbing scan |
| `.mjs` served as JavaScript | otherwise the browser refuses to run the pdf.js worker and PDF upload breaks |
| `try_files … /index.html` | lets a refresh on `/projects` load the app instead of a 404 |

### Phase 10 — Supabase settings

In the Supabase dashboard, open **Authentication → URL Configuration**:

- **Site URL**: `https://arce.example.com`
- **Redirect URLs**: add `https://arce.example.com/**`

The app signs people in with email and password and gets a session straight away, so nothing
redirects today. This only matters if email confirmation or password-reset emails are turned
on later; without it, those links would point at `localhost`.

No database changes are needed if you reuse the current project. A new project needs migrations
`001`-`006` (in `supabase/migrations/`, run in order in the SQL editor), the `materials` table and
the private plan-storage bucket from migration 005.

### Phase 11 — Check it works

Work through this list in a browser at `https://arce.example.com`:

- [ ] The padlock shows, and `http://` redirects to `https://`.
- [ ] `https://arce.example.com/health` answers.
- [ ] Sign in works and the dashboard lists projects.
- [ ] Refreshing `/projects` keeps you on the page (not a 404).
- [ ] **Floor plan:** upload `sample-plans/01-floor-readable.png`. It should price at
      **₱309,364.97**.
- [ ] **PDF:** upload the same drawing saved as a one-page PDF. Same total. If it hangs on
      "Reading your file…", the `.mjs` rule is missing.
- [ ] **Plumbing:** upload `sample-plans/03-plumbing-partial-read.png`. Expect one to two minutes;
      it must finish rather than fail at 60 s.
- [ ] **Restart test:** scan something, run `systemctl restart arce-backend`, then save. If it
      asks for a rescan, a `*_SECRET` is missing from `backend/.env`.
- [ ] `journalctl -u arce-backend -n 50` shows no errors.

---

## 3. Running it

### Deploying an update

Push to `main` from your PC, then on the server:

```bash
sudo bash /opt/arce/deploy/update.sh
```

It pulls, reinstalls Python and Node packages, rebuilds the frontend, restarts the backend and
waits for `/health`. Users mid-scan during the restart get an error and must retry, so update
when nobody is scanning.

**Rolling back:** check out the previous commit and rebuild:

```bash
sudo -u arce -H git -C /opt/arce log --oneline -5   # always as arce, never plain root
sudo -u arce -H git -C /opt/arce checkout <previous-commit>
sudo -u arce -H bash -c 'cd /opt/arce && npm run build' && systemctl restart arce-backend
```

Run `git -C /opt/arce checkout main` before the next `update.sh`.

### Everyday commands

| Task | Command |
| --- | --- |
| Backend logs (live) | `journalctl -u arce-backend -f` |
| Restart backend | `systemctl restart arce-backend` |
| nginx errors | `tail -f /var/log/nginx/error.log` |
| After editing the `materials` table | `systemctl restart arce-backend` (the catalog is cached) |
| Disk / memory | `df -h`, `free -h` |

### Backups

Only two folders on the server hold anything git does not:

- `backend/templates/`: symbols added through the **Symbol Library** screen. Files added
  there are untracked on the server, so a `git pull` keeps them, but losing the VPS loses them.
- `backend/runs/estimates.jsonl`: the audit ledger of every estimate, with assumptions.

Hostinger offers VPS snapshots/backups in hPanel. Turn on whatever your plan includes, or copy
both folders off the server now and then:

```powershell
scp -r root@203.0.113.10:/opt/arce/backend/runs ./server-backup-runs
```

Projects, saved estimates and uploaded plans live in Supabase, so back those up there.

### Known limits on this setup

- **One vCPU:** scans queue, and plumbing takes about two minutes (section 1).
- **Single backend worker:** a crash or restart interrupts scans in progress. systemd restarts it
  within 5 s.
- **PDF uploads of vector drawings** render at 2000 px, a guess untested on a real vector plan
  (see `src/lib/pdf-render-scale.ts`). Check the first CAD-exported PDF a client sends.
- **`/docs` (FastAPI's API explorer) is not exposed.** nginx forwards only `/api/` and
  `/health`.
