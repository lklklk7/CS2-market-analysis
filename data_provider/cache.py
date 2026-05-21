"""Simple JSON file cache with TTL."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

_TTL = int(os.getenv("CACHE_TTL", "86400"))


def _path(key: str) -> Path:
    safe = key.replace("/", "_").replace(" ", "_").replace("|", "-")
    return CACHE_DIR / f"{safe}.json"


def get(key: str) -> dict | list | None:
    p = _path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - data.get("_ts", 0) > _TTL:
            return None
        return data.get("payload")
    except Exception:
        return None


def set(key: str, payload: dict | list) -> None:
    p = _path(key)
    p.write_text(
        json.dumps({"_ts": time.time(), "payload": payload}, ensure_ascii=False),
        encoding="utf-8",
    )
