# Admin Reset Strategy for Restored Local Databases

## Context

After restoring production databases locally, login access may fail even after resetting the password because:

* admin login/email changed
* TOTP / 2FA enabled
* OAuth or SSO modules installed
* custom authentication flows
* inactive admin user

This is especially common in customer production databases.

---

# Recommended Future Command

```bash
dbodoo admin reset
```

Potential future aliases:

```bash
dbodoo local admin-reset
dbodoo admin fix
```

---

# Current Reliable Approach (Odoo 18)

The following shell command successfully resets:

* login
* password
* active status
* TOTP/OTP fields

## Command

```bash
docker compose run --rm -T odoo shell -d devel <<'PY'
user = env['res.users'].browse(2)

vals = {
    'login': 'admin',
    'password': 'admin',
    'active': True,
}

# Only write fields that actually exist
for field in [
    'totp_secret',
    'totp_enabled',
    'otp_enabled',
    'totp_trusted_device_ids',
]:
    if field in user._fields:
        vals[field] = False

user.write(vals)

env.cr.commit()

print("Admin credentials reset successfully")
print("Available TOTP fields:")

for field in user._fields:
    if 'totp' in field or 'otp' in field:
        print("-", field)

PY
```

---

# Notes

## Why `id=2`

Using:

```python
env['res.users'].browse(2)
```

is usually safer than searching by login because:

* customer logins frequently change
* emails become the login
* SSO providers modify login fields

Historically:

* ID 1 = OdooBot
* ID 2 = Administrator

---

# Important Discovery

In Odoo 18:

```python
user.write({'password': 'admin'})
```

works correctly for password reset.

However, resetting password alone is NOT enough if TOTP is enabled.

---

# Important Docker Detail

The `-T` flag is required.

Without it:

```text
the input device is not a TTY
```

because stdin piping conflicts with Docker TTY allocation.

---

# Future Improvements

## Smart Admin Detection

Instead of hardcoding ID 2:

1. Try ID 2
2. Fallback:

   * active internal users
   * non-share users
3. Let user choose

---

# Possible Future Features

## `dbodoo admin reset`

Interactive flow:

* choose database
* choose admin user
* reset login/password
* disable TOTP
* optionally disable OAuth providers

---

# TODO

## SSH Mode

Current backup strategy still depends on:

```text
/web/database/backup
```

Future improvement:

* SSH backup mode
* pg_dump
* rsync filestore
* streaming backup
* large database support
