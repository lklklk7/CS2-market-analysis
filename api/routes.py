"""FastAPI REST routes for the web UI."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

REPORTS_DIR = Path("reports")
WATCHLIST_FILE = Path("watchlist.json")

router = APIRouter(prefix="/api")


def _load_watchlist() -> list[str]:
    if WATCHLIST_FILE.exists():
        try:
            data = WATCHLIST_FILE.read_text(encoding="utf-8").strip()
            if data:
                return json.loads(data)
        except Exception:
            pass
    return [s.strip() for s in os.getenv("SKIN_LIST", "").split(",") if s.strip()]


def _save_watchlist(skins: list[str]) -> None:
    WATCHLIST_FILE.write_text(json.dumps(skins, ensure_ascii=False, indent=2), encoding="utf-8")


class SkinItem(BaseModel):
    market_hash_name: str


@router.get("/watchlist")
def get_watchlist():
    return {"skins": _load_watchlist()}


@router.post("/watchlist")
def add_skin(item: SkinItem):
    skins = _load_watchlist()
    if item.market_hash_name not in skins:
        skins.append(item.market_hash_name)
        _save_watchlist(skins)
    return {"skins": skins}


@router.delete("/watchlist/{market_hash_name:path}")
def remove_skin(market_hash_name: str):
    skins = _load_watchlist()
    skins = [s for s in skins if s != market_hash_name]
    _save_watchlist(skins)
    return {"skins": skins}


_running_task: dict[str, Any] = {"status": "idle", "started_at": None}


@router.post("/analyze/run")
async def trigger_analysis(background_tasks: BackgroundTasks):
    if _running_task["status"] == "running":
        return {"status": "already_running"}
    skins = _load_watchlist()
    if not skins:
        raise HTTPException(400, "Watchlist is empty")

    _running_task["status"] = "running"
    _running_task["started_at"] = date.today().isoformat()

    async def _job():
        try:
            from main import run_analysis
            await run_analysis(skins)
        finally:
            _running_task["status"] = "idle"

    background_tasks.add_task(_job)
    return {"status": "started", "skins": skins}


@router.get("/analyze/status")
def analysis_status():
    return _running_task


@router.get("/reports")
def list_reports():
    REPORTS_DIR.mkdir(exist_ok=True)
    files = sorted(REPORTS_DIR.glob("*.json"), reverse=True)
    return {"dates": [f.stem for f in files]}


@router.get("/reports/{report_date}")
def get_report(report_date: str):
    path = REPORTS_DIR / f"{report_date}.json"
    if not path.exists():
        raise HTTPException(404, f"No report for {report_date}")
    return JSONResponse(json.loads(path.read_text()))


_image_cache: dict[str, str] = {}

@router.get("/skin-image/{market_hash_name:path}")
async def get_skin_image(market_hash_name: str):
    if market_hash_name in _image_cache:
        return {"url": _image_cache[market_hash_name]}

    import urllib.parse
    import httpx

    encoded = urllib.parse.quote(market_hash_name)
    url = (
        f"https://steamcommunity.com/market/search/render/"
        f"?query={encoded}&appid=730&norender=1&count=1"
    )
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CS2SkinTracker/1.0)"}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            r = await client.get(url)
            data = r.json()
            results = data.get("results", [])
            if results:
                icon = results[0].get("asset_description", {}).get("icon_url", "")
                if icon:
                    cdn = f"https://community.cloudflare.steamstatic.com/economy/image/{icon}/360fx360f"
                    _image_cache[market_hash_name] = cdn
                    return {"url": cdn}
    except Exception:
        pass
    return {"url": None}
