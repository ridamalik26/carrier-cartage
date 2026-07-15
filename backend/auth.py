"""Single-admin backend authentication.

This is an internal single-operator tool, so there is exactly one account,
configured via environment variables (ADMIN_USERNAME / ADMIN_PASSWORD_HASH /
AUTH_SALT). Change the credentials with
`python -m backend.set_password <username> <new-password>` — see that script
for details.

Sessions are stateless signed bearer tokens (HMAC-SHA256 over an embedded
expiry, keyed with AUTH_SALT) rather than a server-side session table. That's
required on Vercel — a serverless invocation can't rely on an in-memory dict
surviving until the next request hits a different instance — and it works
identically for local runs. The tradeoff: logout can't force-invalidate a
token before its natural expiry, since there's no server-side revocation
list; it just discards the token client-side.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

TOKEN_TTL_SECONDS = 8 * 60 * 60  # 8 hours


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


def _signing_key() -> bytes:
    salt = os.environ.get("AUTH_SALT", "")
    if not salt:
        raise RuntimeError("AUTH_SALT is not set — run backend.set_password to configure login credentials.")
    return salt.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_token() -> str:
    payload_b64 = _b64url_encode(json.dumps({"exp": time.time() + TOKEN_TTL_SECONDS}).encode("utf-8"))
    sig = hmac.new(_signing_key(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}"


def verify_token(token: str) -> bool:
    if not token or "." not in token:
        return False
    payload_b64, sig_b64 = token.rsplit(".", 1)
    expected_sig = hmac.new(_signing_key(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    try:
        given_sig = _b64url_decode(sig_b64)
    except Exception:
        return False
    if not hmac.compare_digest(expected_sig, given_sig):
        return False
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return False
    return time.time() <= payload.get("exp", 0)


def revoke_token(token: str) -> None:
    """No-op: tokens are stateless (see module docstring) — /api/logout just
    tells the client to drop the token, the server has nothing to clear."""
