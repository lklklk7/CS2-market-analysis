"""AI analysis engine.

Builds a structured prompt from SkinMarketData, calls Claude or an
OpenAI-compatible API, and parses the response into a SkinAnalysis.
"""
from __future__ import annotations

import json
import logging
import os
from textwrap import dedent

from src.models import SkinAnalysis, SkinMarketData

log = logging.getLogger(__name__)

_anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
_openai_key = os.getenv("OPENAI_API_KEY", "")
_openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
_openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")


def _pct(current: float | None, old: float | None) -> float | None:
    if current is None or old is None or old == 0:
        return None
    return round((current - old) / old * 100, 2)


def _build_prompt(data: SkinMarketData) -> str:
    current = data.steam_price or data.skinport_suggested_price or data.csfloat_lowest_price
    chg_7d = _pct(current, data.price_7d_ago)
    chg_30d = _pct(current, data.price_30d_ago)

    lines = [
        f"Skin: {data.market_hash_name}",
        f"Current price (USD): {current}",
        f"Steam volume (24h): {data.steam_volume_24h}",
        f"7-day price change: {chg_7d}%",
        f"30-day price change: {chg_30d}%",
        f"Skinport suggested price: {data.skinport_suggested_price}",
        f"Skinport avg sale price: {data.skinport_avg_sale_price}",
        f"CSFloat listings: {data.csfloat_listing_count}",
        f"CSFloat avg float: {data.csfloat_avg_float}",
        f"CSFloat min float: {data.csfloat_min_float}",
        f"CSFloat lowest listing: {data.csfloat_lowest_price}",
        f"Buff163 price (CNY): {data.buff_price_cny}",
        f"Buff163 price (USD): {data.buff_price_usd}",
        f"Data sources: {', '.join(data.data_sources) or 'Steam only'}",
    ]
    market_block = "\n".join(f"  {l}" for l in lines)

    system = dedent("""\
        You are a CS2 skin market analyst. You analyze price trends, float values,
        supply/demand signals, and market sentiment to give actionable trading signals.
        Be concise and data-driven. Output valid JSON only — no markdown, no extra text.
    """)

    user = dedent(f"""\
        Analyze this CS2 skin and return a JSON object with exactly these fields:

        {{
          "signal": "BUY" | "HOLD" | "SELL",
          "score": 0-100,
          "trend": "Rising" | "Sideways" | "Falling",
          "buy_target": float or null,
          "sell_target": float or null,
          "risks": ["string", ...],
          "catalysts": ["string", ...],
          "float_insight": "string",
          "summary": "1-2 sentence summary"
        }}

        Rules:
        - score >= 65 → BUY, 40-64 → HOLD, < 40 → SELL
        - risks and catalysts: 2-4 items each, specific to this skin
        - float_insight: comment on whether the float/price is favorable
        - buy_target and sell_target in USD (can be null if insufficient data)

        Market data:
        {market_block}
    """)

    return system, user


async def analyze_skin(data: SkinMarketData) -> SkinAnalysis:
    current = data.steam_price or data.skinport_suggested_price or data.csfloat_lowest_price
    chg_7d = _pct(current, data.price_7d_ago)
    chg_30d = _pct(current, data.price_30d_ago)

    system_prompt, user_prompt = _build_prompt(data)
    raw = await _call_ai(system_prompt, user_prompt)
    parsed = _parse_response(raw)

    return SkinAnalysis(
        name=data.name,
        wear=data.wear,
        market_hash_name=data.market_hash_name,
        signal=parsed.get("signal", "HOLD"),
        score=int(parsed.get("score", 50)),
        trend=parsed.get("trend", "Sideways"),
        current_price=current,
        change_7d_pct=chg_7d,
        change_30d_pct=chg_30d,
        volume_7d_avg=data.steam_volume_24h,
        buy_target=parsed.get("buy_target"),
        sell_target=parsed.get("sell_target"),
        risks=parsed.get("risks", []),
        catalysts=parsed.get("catalysts", []),
        float_insight=parsed.get("float_insight", ""),
        summary=parsed.get("summary", ""),
        data_sources=data.data_sources,
    )


async def _call_ai(system: str, user: str) -> str:
    if _anthropic_key:
        return await _call_anthropic(system, user)
    if _openai_key:
        return await _call_openai(system, user)
    raise RuntimeError("No AI API key configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")


async def _call_anthropic(system: str, user: str) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=_anthropic_key)
    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


async def _call_openai(system: str, user: str) -> str:
    import openai

    client = openai.AsyncOpenAI(api_key=_openai_key, base_url=_openai_base)
    resp = await client.chat.completions.create(
        model=_openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content


def _parse_response(raw: str) -> dict:
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as exc:
        log.error("Failed to parse AI response: %s\nRaw: %s", exc, raw[:500])
        return {"signal": "HOLD", "score": 50, "trend": "Sideways", "risks": [], "catalysts": []}
