# dbodoo

Python CLI for Odoo/Doodba database workflows.

Automates remote backup, local restore via Docker Compose, and multi-environment
management — always operating from the current working directory (`Path.cwd()`).

## Installation

Isolated install with `pipx` (recommended):

```bash
pipx install dbodoo
```

Local development:

```bash
pipx install --editable .
# or
pip install -e .
```

## Quick start

```bash
cd ~/projects/my-doodba-project

# 1. Download a backup from the remote server
dbodoo remote -b

# 2. Restore the downloaded ZIP into the local database
dbodoo remote -r

# 3. Or do both in one step
dbodoo remote -b -r
```

If `.remotes.json` does not exist yet, the configuration wizard starts
automatically on the first command.

---

## Commands

### `dbodoo init`

Create or update `.remotes.json` with an interactive wizard.

```bash
dbodoo init
```

The wizard asks:

1. **Mode** — determines which fields are required:
   - **Backup + Restore** — downloads the ZIP and restores locally (URL + password + dbname)
   - **Backup only** — downloads the ZIP only (URL + password + dbname)
   - **Restore only** — restores an existing ZIP (dbname only)
2. Remote name (backup modes), database name, URL, and password

If `.remotes.json` already exists, the wizard offers to add another remote or
overwrite the file. Use `--force` to overwrite without prompting.

**Non-interactive (CI / scripts):**

```bash
# Backup + Restore
dbodoo init --name prod --dbname prod \
            --remote-address https://client.odoo.com/ \
            --password masterpassword

# Restore-only (no URL or password needed)
dbodoo init --name prod --dbname prod
```

---

### `dbodoo remote -b`

Download a backup ZIP from the remote Odoo server.

```bash
dbodoo remote -b
```

- Connects to `https://<remote_address>/web/database/backup`
- Shows a Rich progress bar during the download
- Saves to `../<dbname>.zip` (one level above the project root)
- Distinct error messages for: timeout, connection failure, wrong password
  (Odoo returns HTML instead of a ZIP), HTTP 4xx/5xx

---

### `dbodoo remote -r`

Restore the last downloaded ZIP into the local database via Docker Compose.

```bash
dbodoo remote -r

# Restore into a database other than 'devel' (the default)
dbodoo remote -r --destination-db staging
```

- Expects the ZIP at `../<dbname>.zip` — run `-b` first if it does not exist
- Detects Docker Compose v2 (`docker compose`) with fallback to v1 (`docker-compose`)
- Runs `click-odoo-restoredb` inside the `odoo` service via a read-only bind-mount
- If the destination database already exists, asks whether to rerun with `--force`
  (drops and recreates the database) — never forces automatically
- Emits a warning if the directory does not look like a Doodba project (missing
  markers), but does not block

---

### `dbodoo remote -b -r`

Download a backup and restore it in a single step.

```bash
dbodoo remote -b -r

# With an explicit destination database
dbodoo remote -b -r --destination-db staging
```

If the download fails, the restore is never attempted.

---

### `dbodoo admin reset`

Reset an Odoo admin user: login, password, TOTP 2FA, and active status.

```bash
# Reset to defaults (login=admin, password=admin, user id=2, db=devel)
dbodoo admin reset

# Custom credentials
dbodoo admin reset --login admin --password secret

# Different user or database
dbodoo admin reset --user-id 3
dbodoo admin reset --db staging

# Keep 2FA settings untouched
dbodoo admin reset --keep-2fa
```

Before running, the command always shows the target database and asks for
confirmation — press **Enter** to accept or type a different name:

```text
Local database name: (devel)
```

Runs a `click-odoo` script inside the `odoo` Docker Compose service (same
container as `dbodoo remote -r`) with a read-only bind-mount, so no extra
volume configuration is required.

What the reset does:

| Action | Default |
| --- | --- |
| Set `active = True` | always |
| Set `login` | `admin` |
| Set password | `admin` |
| NULL `totp_secret` (disable 2FA) | yes (`--disable-2fa`) |

**Options:**

| Flag | Default | Description |
| --- | --- | --- |
| `--login TEXT` | `admin` | New login for the user |
| `--password TEXT` | `admin` | New plain-text password |
| `--user-id INT` | `2` | Database id of the user |
| `--db TEXT` | `devel` | Local database name |
| `--disable-2fa` / `--keep-2fa` | `--disable-2fa` | Whether to disable TOTP |

---

### `dbodoo neutralize mail`

Disable all outgoing mail servers in a restored local database to prevent
accidental email delivery to real customers.

```bash
# Neutralize the default 'devel' database
dbodoo neutralize mail

# Neutralize a different database
dbodoo neutralize mail --db staging
```

Before running, the command asks you to confirm (or change) the target
database — press **Enter** to accept or type a different name:

```text
Local database name: (devel)
```

What it does:

```sql
UPDATE ir_mail_server SET active = FALSE WHERE active = TRUE;
```

> **Note:** Direct SQL is used instead of the ORM because Odoo 18 added a
> constraint in `ir.mail_server.write()` that refuses to archive servers
> still referenced by email templates. SQL bypasses that check while remaining
> safe for local use.

Expected output:

```text
Neutralizing outgoing mail (db=devel)…
Found 2 mail server(s).
All outgoing mail servers disabled successfully.
✓ Mail neutralization complete.
```

Uses `docker compose run --rm -T odoo shell -d {db}` with stdin piping — no
external dependencies beyond core Odoo.

**Options:**

| Flag | Default | Description |
| --- | --- | --- |
| `--db TEXT` | `devel` | Local database name |

---

### `dbodoo choose`

Select and print a remote name (useful in scripts).

```bash
dbodoo choose
```

With a single remote configured, selection is automatic.

---

## `.remotes.json` structure

The file lives at the project root, next to `docker-compose.yml`.

**Backup + Restore / Backup only:**

```json
{
  "prod": {
    "remote_address": "client.odoo.com",
    "dbname": "prod",
    "password": "masterpassword"
  },
  "staging": {
    "remote_address": "staging.client.odoo.com",
    "dbname": "staging",
    "password": "masterpassword"
  }
}
```

**Restore only** (no remote connection required):

```json
{
  "prod": {
    "dbname": "prod"
  }
}
```

URLs are normalised on save: `https://client.odoo.com:8069/` → `client.odoo.com:8069`.

---

## Project detection

dbodoo locates the project root by walking up from `cwd`, looking for:

1. `.remotes.json`
2. Doodba markers: `common.yaml`, `docker-compose.yml`, `odoo/custom/src`

Configuration is always local to the project — there is no global config file.

---

## Troubleshooting

### Backup ZIP not found

```text
Error: Backup ZIP not found at /home/.../project.zip.
Run dbodoo remote -b first to download it.
```

Run `dbodoo remote -b` before attempting a restore.

---

### Wrong master password

```text
Error: Authentication failed for 'client.odoo.com'. The server returned
an HTML page instead of a ZIP. Check the master password.
```

Check the password in `.remotes.json` or run `dbodoo init` to update it.

---

### Destination database already exists

```text
Error: Destination database already exists: devel
⚠  click-odoo-restoredb exited with code 1.
? Rerun with --force? (drops and recreates the 'devel' database) (y/N)
```

Answer `y` to drop and recreate the database, or `n` to cancel without
touching anything.

---

### Docker Compose not found

```text
Error: Docker Compose not found. Install Docker with the Compose plugin (v2)
or 'docker-compose' (v1).
```

Install [Docker Desktop](https://docs.docker.com/get-docker/) or the Compose
plugin: `apt install docker-compose-plugin`.

---

### Directory does not look like a Doodba project

```text
Warning: This directory does not look like a Doodba project
(missing: common.yaml, docker-compose.yml, odoo/custom/src).
The Docker restore may not work as expected.
```

The restore continues, but may fail if the `odoo` service is not defined in
`docker-compose.yml`. Run dbodoo from the Doodba project root.

---

### `.remotes.json` not found

The `remote` command starts the configuration wizard automatically. To create
the file manually:

```bash
dbodoo init
```
