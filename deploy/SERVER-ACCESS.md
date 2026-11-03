# Getting into the ARCE server from another device

How to open a terminal on the production server (https://arce-app.tech, see
[PRODUCTION.md](PRODUCTION.md)) from a laptop or PC that has never connected before.
No passwords or keys are stored in this file, and none should be.

| | |
| --- | --- |
| Server address | `arce-app.tech` (or the IP `187.124.141.84`) |
| User | `root` |
| How you log in | an **SSH key**: a file pair made on each device |
| Emergency way in | hPanel's **browser terminal**: works from any browser, no key needed |

**One key per device.** Make a new key on each laptop and add it to the server. Do not copy the
private key file from another computer: if one device is lost, you then remove just that key
(section 5) and the others keep working.

---

## 1. Check the device has SSH

- **Windows 10/11:** open **PowerShell** and run `ssh -V`. It prints a version. If not: Settings →
  System → Optional features → add **OpenSSH Client**.
- **macOS / Linux:** open **Terminal**; `ssh` is already there.

## 2. Make a key on the new device

```powershell
ssh-keygen -t ed25519 -C "arce-<device name>"
```

- **"Enter file in which to save the key":** press Enter for the default. If it says the file
  already exists, type `n` and use the existing key instead (skip to step 3).
- **Passphrase:** pick one you will remember, or press Enter twice for none. It protects the key
  if the device is stolen, but you type it at every login. **There is no way to recover a forgotten
  passphrase** - you would make a new key.

Show the **public** key (the only part you ever share):

- Windows: `Get-Content $HOME\.ssh\id_ed25519.pub`
- macOS / Linux: `cat ~/.ssh/id_ed25519.pub`

It is one line starting `ssh-ed25519 AAAA...` and ending with the comment you gave. The other
file, `id_ed25519` without `.pub`, is the private key: never paste or send it anywhere.

## 3. Add the public key to the server

Pick whichever way in you have:

**A. From a device that can already log in** (for example your main PC):

```bash
ssh root@arce-app.tech
```

then on the server, with the new device's whole `ssh-ed25519 ...` line between the quotes:

```bash
echo 'ssh-ed25519 AAAA...paste-the-whole-line...' >> ~/.ssh/authorized_keys
```

**B. From hPanel's browser terminal** (no other device needed): hPanel → **VPS** → your server
(`srv2123384.hstgr.cloud`) → **Browser terminal** (Hostinger may label it Terminal), then run the
same `echo ... >> ~/.ssh/authorized_keys` line there.

**C. With the root password**, only while password login is still switched on
([PRODUCTION.md](PRODUCTION.md) lists whether it is). From the new device:

- Windows:

  ```powershell
  Get-Content $HOME\.ssh\id_ed25519.pub | ssh root@arce-app.tech "cat >> ~/.ssh/authorized_keys"
  ```

- macOS / Linux: `ssh-copy-id root@arce-app.tech`

Use `>>` (append), never `>` - a single `>` would replace the file and lock out every other device.

## 4. Connect

```powershell
ssh root@arce-app.tech
```

- The first time, it asks whether to trust the server. Type the whole word **`yes`** (not `y`).
- If it asks for a **passphrase**, that is the key's passphrase from step 2, not a server password.
- You are in when the prompt reads `root@srv2123384:~#`.

If it asks for `root@arce-app.tech's password` instead, the server did not accept the key: either
the passphrase was wrong three times (SSH then falls back to the password) or step 3 did not save
the key. Check the line is in the server's `~/.ssh/authorized_keys` (way **B** works for this).

**Optional shortcut.** Add this to `~/.ssh/config` on the device (on Windows,
`C:\Users\<you>\.ssh\config`, created if missing), then just run `ssh arce`:

```
Host arce
    HostName arce-app.tech
    User root
    IdentityFile ~/.ssh/id_ed25519
```

**Stop typing the passphrase every time** (Windows; once per device, PowerShell as Administrator):

```powershell
Get-Service ssh-agent | Set-Service -StartupType Automatic; Start-Service ssh-agent
```

then, in a normal PowerShell: `ssh-add $HOME\.ssh\id_ed25519`. On macOS: `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`.

## 5. Removing a device (lost, sold, replaced)

On the server, list the keys with line numbers:

```bash
nl -ba ~/.ssh/authorized_keys
```

Each line ends with the comment from step 2 (`arce-<device name>`). Delete that device's line,
for example line 3:

```bash
sed -i '3d' ~/.ssh/authorized_keys
```

Check you are still allowed in from another window before closing this one.

## 6. Copying files to and from the server

`scp` uses the same key. From the device, not from inside the server:

```powershell
scp backend\.env root@arce-app.tech:/opt/arce/backend/.env
scp root@arce-app.tech:/opt/arce/backend/runs/estimates.jsonl .
```

After replacing a `.env` file, fix its owner and permissions on the server:

```bash
chown arce:arce /opt/arce/backend/.env && chmod 600 /opt/arce/backend/.env && systemctl restart arce-backend
```

## 7. Once you are in

| Task | Command |
| --- | --- |
| Is the app healthy? | `curl -s http://127.0.0.1:8000/health` |
| Backend log | `journalctl -u arce-backend -n 50` |
| Restart the backend | `systemctl restart arce-backend` |
| Deploy the latest `main` | `sudo bash /opt/arce/deploy/update.sh` |
| Disk and memory | `df -h` and `free -h` |
| Leave the server | `exit` |

More in [PRODUCTION.md](PRODUCTION.md) and [HOSTINGER.md](HOSTINGER.md), section 3.

## Safety

- **Keep the browser terminal as the way back in.** It needs only your Hostinger login, so it
  works even if every key is lost. Protect the Hostinger account with a strong password and
  two-factor authentication.
- **Before switching off password login** (HOSTINGER.md, Phase 3), make sure at least one key logs
  in. Afterwards, way **C** above stops working, and new devices are added with **A** or **B**.
- **Never share** the private key, the root password, or the server's `.env` files.
