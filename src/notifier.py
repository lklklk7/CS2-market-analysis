"""Notification senders: Discord, Slack."""
from __future__ import annotations

import logging
import os
from datetime import date

import httpx

from src.models import DailyReport, SkinAnalysis

log = logging.getLogger(__name__)

_discord_url = os.getenv("DISCORD_WEBHOOK_URL", "")
_slack_token = os.getenv("SLACK_BOT_TOKEN", "")
_slack_channel = os.getenv("SLACK_CHANNEL_ID", "")

SIGNAL_EMOJI = {"BUY": "🟢", "HOLD": "🟡", "SELL": "🔴"}
TREND_ARROW = {"Rising": "📈", "Sideways": "➡️", "Falling": "📉"}


def _fmt_price(v: float | None) -> str:
    return f"${v:.2f}" if v is not None else "N/A"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def _skin_block(s: SkinAnalysis) -> str:
    em = SIGNAL_EMOJI.get(s.signal, "⚪")
    lines = [
        f"{'─'*40}",
        f"{em} {s.market_hash_name} — {s.signal} | Score: {s.score} | {TREND_ARROW.get(s.trend,'')} {s.trend}",
        f"💰 Current: {_fmt_price(s.current_price)} | 7d: {_fmt_pct(s.change_7d_pct)} | 30d: {_fmt_pct(s.change_30d_pct)}",
    ]
    if s.volume_7d_avg is not None:
        lines.append(f"📦 Volume (24h): {s.volume_7d_avg:,}")
    if s.buy_target or s.sell_target:
        lines.append(f"🎯 Buy target: {_fmt_price(s.buy_target)} | Sell target: {_fmt_price(s.sell_target)}")
    if s.float_insight:
        lines.append(f"🔬 Float: {s.float_insight}")
    if s.risks:
        lines.append("⚠️  Risks:")
        for r in s.risks:
            lines.append(f"   • {r}")
    if s.catalysts:
        lines.append("✨ Catalysts:")
        for c in s.catalysts:
            lines.append(f"   • {c}")
    if s.summary:
        lines.append(f"📝 {s.summary}")
    return "\n".join(lines)


def build_message(report: DailyReport) -> str:
    header = [
        f"🎮 {report.date} CS2 Skin Dashboard",
        f"Analyzed {len(report.skins)} skin(s) | "
        f"🟢 Buy: {report.buy_count}  🟡 Hold: {report.hold_count}  🔴 Sell: {report.sell_count}",
        "",
        "📊 Summary",
    ]
    for s in report.skins:
        em = SIGNAL_EMOJI.get(s.signal, "⚪")
        header.append(f"{em} {s.market_hash_name} — {s.signal} | Score: {s.score} | {s.trend}")

    detail = ["", "━" * 40, "📈 Detailed Analysis", ""]
    for s in report.skins:
        detail.append(_skin_block(s))
        detail.append("")

    return "\n".join(header + detail)


async def send_discord(report: DailyReport) -> bool:
    if not _discord_url:
        log.debug("Discord webhook not configured")
        return False
    msg = build_message(report)
    # Discord has a 2000-char limit per message; split if needed
    chunks = [msg[i : i + 1990] for i in range(0, len(msg), 1990)]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for chunk in chunks:
                r = await client.post(_discord_url, json={"content": f"```\n{chunk}\n```"})
                r.raise_for_status()
        log.info("Discord notification sent (%d chunk(s))", len(chunks))
        return True
    except Exception as exc:
        log.error("Discord send failed: %s", exc)
        return False



async def send_slack(report: DailyReport) -> bool:
    if not _slack_token or not _slack_channel:
        log.debug("Slack not configured")
        return False
    msg = build_message(report)
    url = "https://slack.com/api/chat.postMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {_slack_token}"},
                json={"channel": _slack_channel, "text": msg},
            )
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                log.error("Slack API error: %s", data.get("error"))
                return False
        log.info("Slack notification sent")
        return True
    except Exception as exc:
        log.error("Slack send failed: %s", exc)
        return False


async def notify_all(report: DailyReport) -> dict[str, bool]:
    import asyncio

    results = await asyncio.gather(
        send_discord(report),
        send_slack(report),
        return_exceptions=False,
    )
    return {"discord": results[0], "slack": results[1]}
