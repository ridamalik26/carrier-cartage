"""Single-admin backend authentication.

This is an internal single-operator tool, so there is exactly one account,
configured via environment variables (ADMIN_USERNAME / ADMIN_PASSWORD_HASH /
AUTH_SALT in .env) rather than a users table. Change the credentials with
`python -m backend.set_password <username> <new-password>` — see that script
for details. Sessions are opaque bearer tokens held in memory; they reset
whenever the server restarts, which is fine for a tool that's started fresh
each evaluation cycle via start.bat/start.sh.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

TOKEN_TTL_SECONDS = 8 * 60 * 60  # 8 hours

_active_tokens: dict[str, float] = {}


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()


def verify_credentials(username: str, password: str) -> bool:
    expected_user = os.environ.get("ADMIN_USERNAME", "")
    expected_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")
    salt = os.environ.get("AUTH_SALT", "")
    if not expected_user or not expected_hash or not salt:
        return False
    if not hmac.compare_digest(username, expected_user):
        return False
    return hmac.compare_digest(hash_password(password, salt), expected_hash)


def issue_token() -> str:
    token = secrets.token_urlsafe(32)
    _active_tokens[token] = time.time() + TOKEN_TTL_SECONDS
    return token


def verify_token(token: str) -> bool:
    if not token:
        return False
    expiry = _active_tokens.get(token)
    if expiry is None:
        return False
    if time.time() > expiry:
        _active_tokens.pop(token, None)
        return False
    return True


def revoke_token(token: str) -> None:
    _active_tokens.pop(token, None)
