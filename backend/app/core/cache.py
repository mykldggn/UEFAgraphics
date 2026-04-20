"""
Disk cache for generated infographic images and scraped data.
Keys are hex MD5 digests of the (type, params) tuple.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from app.config import settings


def _cache_dir() -> Path:
    p = Path(settings.CACHE_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _key(namespace: str, params: dict) -> str:
    raw = json.dumps({"ns": namespace, **params}, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def img_get(namespace: str, params: dict, ttl_hours: int = 24) -> bytes | None:
    path = _cache_dir() / f"{_key(namespace, params)}.png"
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl_hours * 3600:
        path.unlink(missing_ok=True)
        return None
    return path.read_bytes()


def img_save(namespace: str, params: dict, data: bytes) -> None:
    path = _cache_dir() / f"{_key(namespace, params)}.png"
    path.write_bytes(data)


def json_get(namespace: str, params: dict, ttl_hours: int = 24) -> dict | list | None:
    path = _cache_dir() / f"{_key(namespace, params)}.json"
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl_hours * 3600:
        path.unlink(missing_ok=True)
        return None
    return json.loads(path.read_text())


def json_save(namespace: str, params: dict, data: dict | list) -> None:
    path = _cache_dir() / f"{_key(namespace, params)}.json"
    path.write_text(json.dumps(data))
