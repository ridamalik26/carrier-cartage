"""Change the login username/password.

Run this any time you want to change who can sign in:

    python -m backend.set_password <username> <new-password>

It writes ADMIN_USERNAME, ADMIN_PASSWORD_HASH and AUTH_SALT into the .env
file at the project root (creating it if missing), replacing any previous
values for those three keys and leaving everything else in .env untouched.
Restart the server afterwards for the change to take effect.
"""
from __future__ import annotations

import os
import secrets
import sys

from backend.auth import hash_password

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")

MANAGED_KEYS = ("ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "AUTH_SALT")


def upsert_env(path: str, values: dict[str, str]) -> None:
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    seen = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if "=" in stripped and not stripped.startswith("#") else None
        if key in values:
            new_lines.append(f"{key}={values[key]}\n")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in values.items():
        if key not in seen:
            new_lines.append(f"{key}={value}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m backend.set_password <username> <new-password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    upsert_env(ENV_PATH, {
        "ADMIN_USERNAME": username,
        "ADMIN_PASSWORD_HASH": password_hash,
        "AUTH_SALT": salt,
    })
    print(f"Updated {ENV_PATH} — username set to {username!r}. Restart the server to apply.")


if __name__ == "__main__":
    main()
