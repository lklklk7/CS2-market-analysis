#!/usr/bin/env python3
"""CS2 Skin Tracker — CLI entrypoint.

Usage examples:
  python main.py
  python main.py --skins "AK-47 | Redline (Field-Tested)" "AWP | Asiimov (Battle-Scarred)"
  python main.py --dry-run
  python main.py --debug
  python main.py --schedule
  python main.py --serve-only
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy libraries
    for lib in ("httpx", "httpcore", "anthropic", "openai"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def _load_skin_list(cli_skins: list[str] | None) -> list[str]:
    if cli_skins:
        return [s.strip() for s in cli_skins if s.strip()]
    env_val = os.getenv("SKIN_LIST", "")
    if env_val:
        return [s.strip() for s in env_val.split(",") if s.strip()]
    sys.exit("No skins configured. Set SKIN_LIST in .env or pass --skins.")


async def run_analysis(skins: list[str], dry_run: bool = False) -> dict:
    from data_provider.aggregator import fetch_skin
    from src.analyzer import analyze_skin
    from src.models import DailyReport
    from src.notifier import build_message, notify_all

    today = date.today().isoformat()
    log = logging.getLogger("main")
    log.info("Starting analysis for %d skin(s): %s", len(skins), skins)

    analyses = []
    for skin in skins:
        log.info("Processing: %s", skin)
        try:
            market_data = await fetch_skin(skin)
            analysis = await analyze_skin(market_data)
            analyses.append(analysis)
            signal_map = {"BUY": "🟢", "HOLD": "🟡", "SELL": "🔴"}
            print(
                f"  {signal_map.get(analysis.signal,'⚪')} {skin} → "
                f"{analysis.signal} (score={analysis.score}) "
                f"price=${analysis.current_price or 0:.2f}"
            )
        except Exception as exc:
            log.error("Failed to process %s: %s", skin, exc)

    report = DailyReport(date=today, skins=analyses)

    # Persist report
    report_path = REPORTS_DIR / f"{today}.json"
    report_path.write_text(
        json.dumps(report.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Report saved: %s", report_path)

    # Print dashboard
    print("\n" + "=" * 50)
    print(build_message(report))
    print("=" * 50 + "\n")

    if not dry_run:
        results = await notify_all(report)
        for channel, ok in results.items():
            if ok:
                log.info("✓ %s notification sent", channel)
    else:
        log.info("Dry-run mode — notifications skipped")

    return report.model_dump()


def main() -> None:
    parser = argparse.ArgumentParser(description="CS2 Skin Tracker")
    parser.add_argument("--skins", nargs="+", metavar="SKIN", help="Override SKIN_LIST")
    parser.add_argument("--dry-run", action="store_true", help="Skip notifications")
    parser.add_argument("--debug", action="store_true", help="Verbose logging")
    parser.add_argument("--schedule", action="store_true", help="Run on cron schedule")
    parser.add_argument("--serve-only", action="store_true", help="Start web UI only")
    args = parser.parse_args()

    _setup_logging(args.debug or os.getenv("DEBUG", "").lower() == "true")

    if args.serve_only:
        import uvicorn
        from server import app

        uvicorn.run(app, host="0.0.0.0", port=8000)
        return

    skins = _load_skin_list(args.skins)

    if args.schedule:
        from src.scheduler import run_schedule

        async def job():
            await run_analysis(skins, dry_run=args.dry_run)

        run_schedule(job)
    else:
        asyncio.run(run_analysis(skins, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
