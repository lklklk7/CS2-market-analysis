from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    timestamp: str
    price: float


class SkinMarketData(BaseModel):
    name: str
    wear: str
    market_hash_name: str

    # Steam
    steam_price: float | None = None
    steam_volume_24h: int | None = None
    steam_price_history: list[PricePoint] = Field(default_factory=list)

    # Skinport
    skinport_suggested_price: float | None = None
    skinport_avg_sale_price: float | None = None

    # CSFloat
    csfloat_avg_float: float | None = None
    csfloat_min_float: float | None = None
    csfloat_listing_count: int | None = None
    csfloat_lowest_price: float | None = None

    # Buff163
    buff_price_cny: float | None = None
    buff_price_usd: float | None = None

    # Derived
    price_7d_ago: float | None = None
    price_30d_ago: float | None = None

    data_sources: list[str] = Field(default_factory=list)


class SkinAnalysis(BaseModel):
    name: str
    wear: str
    market_hash_name: str
    signal: Literal["BUY", "HOLD", "SELL"]
    score: int = Field(ge=0, le=100)
    trend: Literal["Rising", "Sideways", "Falling"]

    current_price: float | None = None
    change_7d_pct: float | None = None
    change_30d_pct: float | None = None
    volume_7d_avg: float | None = None

    buy_target: float | None = None
    sell_target: float | None = None

    risks: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    float_insight: str = ""
    summary: str = ""

    data_sources: list[str] = Field(default_factory=list)


class DailyReport(BaseModel):
    date: str
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    skins: list[SkinAnalysis] = Field(default_factory=list)

    @property
    def buy_count(self) -> int:
        return sum(1 for s in self.skins if s.signal == "BUY")

    @property
    def hold_count(self) -> int:
        return sum(1 for s in self.skins if s.signal == "HOLD")

    @property
    def sell_count(self) -> int:
        return sum(1 for s in self.skins if s.signal == "SELL")
