"""Steam Community Market adapter.

Steam's public endpoints are aggressive with rate-limiting; we use a 3-second
delay between calls and a 24-hour cache so repeated runs don't get throttled.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx

from . import cache

log = logging.getLogger(__name__)

APP_ID = os.getenv("STEAM_APP_ID", "730")
CURRENCY = os.getenv("STEAM_CURRENCY", "1")  # 1 = USD

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CS2SkinTracker/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}

_last_call: float = 0.0


async def _rate_limit() -> None:
    global _last_call
    import time

    elapsed = time.monotonic() - _last_call
    if elapsed < 3.0:
        await asyncio.sleep(3.0 - elapsed)
    _last_call = time.monotonic()


async def get_price_overview(market_hash_name: str) -> dict | None:
    """Return lowest_price, median_price, volume for a skin."""
    cache_key = f"steam_overview_{market_hash_name}"
    cached = cache.get(cache_key)
    if cached is not None:
        log.debug("steam overview cache hit: %s", market_hash_name)
        return cached

    await _rate_limit()
    encoded = urllib.parse.quote(market_hash_name)
    url = (
        f"https://steamcommunity.com/market/priceoverview/"
        f"?appid={APP_ID}&currency={CURRENCY}&market_hash_name={encoded}"
    )
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            if not data.get("success"):
                log.warning("Steam overview not successful for %s", market_hash_name)
                return None
            cache.set(cache_key, data)
            return data
    except Exception as exc:
        log.error("Steam overview error for %s: %s", market_hash_name, exc)
        return None


def _parse_price(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", raw.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_volume(raw: str | None) -> int | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d]", "", raw)
    try:
        return int(cleaned)
    except ValueError:
        return None


async def get_current_price(market_hash_name: str) -> tuple[float | None, int | None]:
    """Return (price_usd, volume_24h)."""
    data = await get_price_overview(market_hash_name)
    if not data:
        return None, None
    price = _parse_price(data.get("median_price") or data.get("lowest_price"))
    volume = _parse_volume(data.get("volume"))
    return price, volume


async def get_price_history(market_hash_name: str) -> list[dict]:
    """
    Return a list of {timestamp, price} dicts from the local snapshot history.
    Steam's pricehistory endpoint requires auth cookies; instead we read from
    our own cached daily snapshots stored in cache/history_{name}.json.
    """
    cache_key = f"steam_history_{market_hash_name}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # No history yet — seed with today's price so future runs have data
    price, _ = await get_current_price(market_hash_name)
    if price is None:
        return []

    now = datetime.now(timezone.utc)
    history = [{"timestamp": now.isoformat(), "price": price}]
    cache.set(cache_key, history)
    return history


def derive_changes(
    history: list[dict],
) -> tuple[float | None, float | None, float | None]:
    """Return (price_7d_ago, price_30d_ago, current) from snapshot history."""
    if not history:
        return None, None, None

    now = datetime.now(timezone.utc)
    target_7d = now - timedelta(days=7)
    target_30d = now - timedelta(days=30)

    def closest(target: datetime) -> float | None:
        best = None
        best_delta = None
        for pt in history:
            try:
                ts = datetime.fromisoformat(pt["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                delta = abs((ts - target).total_seconds())
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best = pt["price"]
            except Exception:
                continue
        return best

    current = history[-1]["price"] if history else None
    return closest(target_7d), closest(target_30d), current
