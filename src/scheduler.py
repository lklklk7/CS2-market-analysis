"""APScheduler wrapper for local --schedule mode."""
from __future__ import annotations

import asyncio
import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

_cron = os.getenv("SCHEDULE_CRON", "0 9 * * *")


def _parse_cron(expr: str) -> dict:
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5-field cron expression, got: {expr!r}")
    minute, hour, day, month, dow = parts
    return dict(minute=minute, hour=hour, day=day, month=month, day_of_week=dow)


def run_schedule(job_fn) -> None:
    """Block forever, running job_fn() on the configured cron schedule."""
    scheduler = BlockingScheduler(timezone="UTC")
    cron_kwargs = _parse_cron(_cron)
    log.info("Scheduling job with cron: %s (UTC)", _cron)

    def _wrapper():
        asyncio.run(job_fn())

    scheduler.add_job(_wrapper, CronTrigger(**cron_kwargs), id="daily_analysis")
    log.info("Scheduler started. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
