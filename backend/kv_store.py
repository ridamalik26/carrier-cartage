"""Minimal Vercel KV (Upstash Redis REST API) client, used to stash the app's
in-memory AppState as JSON between otherwise-stateless serverless
invocations — see main.py's auth_gate middleware, which loads this before
each /api/* request and saves it back after.
"""
from __future__ import annotations

import json
import os

import httpx


def _url() -> str:
    url = os.environ.get("KV_REST_API_URL")
    if not url:
        raise RuntimeError("KV_REST_API_URL is not set — add the Vercel KV integration to this project.")
    return url.rstrip("/")


def _token() -> str:
    token = os.environ.get("KV_REST_API_TOKEN")
    if not token:
        raise RuntimeError("KV_REST_API_TOKEN is not set — add the Vercel KV integration to this project.")
    return token


def _command(*args) -> object:
    resp = httpx.post(_url(), json=list(args), headers={"authorization": f"Bearer {_token()}"}, timeout=10.0)
    resp.raise_for_status()
    return resp.json().get("result")


def get_json(key: str, default=None):
    raw = _command("GET", key)
    if raw is None:
        return default
    return json.loads(raw)


def set_json(key: str, value) -> None:
    _command("SET", key, json.dumps(value))
