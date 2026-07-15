"""Minimal Vercel Blob REST client, called directly over HTTP since there's no
official Python SDK. Wire format reverse-engineered from @vercel/blob's JS
source (dist/chunk-CIIQSN42.js in the npm package): base URL, headers, and
response shape below. Used instead of local disk because Vercel serverless
functions have a read-only/ephemeral filesystem per invocation.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx

_API_BASE = "https://vercel.com/api/blob"
_API_VERSION = "12"


def _token() -> str:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is not set — add the Vercel Blob integration to this project.")
    return token


def put_blob(pathname: str, data: bytes, content_type: str) -> dict:
    """Uploads (or overwrites) a blob. Returns its metadata, including "url"
    (needed to read it back later — private blobs require the same bearer
    token to fetch)."""
    resp = httpx.put(
        f"{_API_BASE}/?{urlencode({'pathname': pathname})}",
        content=data,
        headers={
            "authorization": f"Bearer {_token()}",
            "x-api-version": _API_VERSION,
            "x-content-type": content_type,
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
            "x-vercel-blob-access": "private",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def get_blob_bytes(url: str) -> bytes:
    resp = httpx.get(url, headers={"authorization": f"Bearer {_token()}"}, timeout=30.0)
    resp.raise_for_status()
    return resp.content


def delete_blobs(urls: list[str]) -> None:
    if not urls:
        return
    resp = httpx.post(
        f"{_API_BASE}/delete",
        json={"urls": urls},
        headers={
            "authorization": f"Bearer {_token()}",
            "x-api-version": _API_VERSION,
            "content-type": "application/json",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
