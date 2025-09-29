"""Generate daily Base-chain summary content backed by stored momentum snapshots."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional

from services.geckoterminal_client import GeckoTerminalClient
from services.coingecko_client import CoinGeckoClient
from storage.sqlite_repository import SQLiteRepository


@dataclass
class TokenRollup:
    symbol: str
    alerts: int = 0
    scores: List[float] = field(default_factory=list)
    effective_volume: float = 0.0
    net_profit: float = 0.0
    dominant_buy_alerts: int = 0
    dominant_sell_alerts: int = 0
    max_score: float = 0.0
    base_token_address: Optional[str] = None
    coingecko_id: Optional[str] = None
    gecko_metrics: Dict[str, Optional[float]] = field(default_factory=dict)
    coingecko_market: Dict[str, Optional[float]] = field(default_factory=dict)

    def record(self, payload: Dict[str, Any], momentum_score: float, net_profit_usd: float) -> None:
        self.alerts += 1
        self.scores.append(momentum_score)
        self.max_score = max(self.max_score, momentum_score)
        self.effective_volume += float(payload.get("effective_volume_usd") or 0.0)
        self.net_profit += net_profit_usd

        flow_side = payload.get("dominant_flow_side")
        if flow_side == "buy":
            self.dominant_buy_alerts += 1
        elif flow_side == "sell":
            self.dominant_sell_alerts += 1

        base_addr = (payload.get("base_token_address") or payload.get("token_address"))
        if base_addr and not self.base_token_address:
            self.base_token_address = str(base_addr).lower()

        coingecko_id = payload.get("coingecko_id")
        if coingecko_id and not self.coingecko_id:
            self.coingecko_id = coingecko_id

    @property
    def avg_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def momentum_skew(self) -> str:
        if self.dominant_buy_alerts > self.dominant_sell_alerts:
            return "buy"
        if self.dominant_sell_alerts > self.dominant_buy_alerts:
            return "sell"
        return "flat"


@dataclass
class DailySummaryResult:
    generated_at: datetime
    window_start: datetime
    token_rollups: List[TokenRollup]
    total_alerts: int
    total_tokens: int
    median_score: Optional[float]
    tweet_text: Optional[str]

    @property
    def has_content(self) -> bool:
        return bool(self.tweet_text)


class BaseDailySummaryBuilder:
    """Assemble a once-per-day Base chain summary suitable for Twitter."""

    def __init__(
        self,
        *,
        repository: SQLiteRepository,
        geckoterminal_client: GeckoTerminalClient,
        coingecko_client: CoinGeckoClient,
        network: str = "base",
    ) -> None:
        self._repository = repository
        self._gecko = geckoterminal_client
        self._coingecko = coingecko_client
        self._network = network

    async def build(self, *, window_hours: int = 24, max_tokens: int = 3) -> DailySummaryResult:
        generated_at = datetime.now(timezone.utc)
        window_start = generated_at - timedelta(hours=window_hours)

        records = await self._repository.fetch_momentum_records(
            limit=1000,
            token=None,
            direction=None,
            chain=self._network,
            since=window_start,
        )

        if not records:
            return DailySummaryResult(
                generated_at=generated_at,
                window_start=window_start,
                token_rollups=[],
                total_alerts=0,
                total_tokens=0,
                median_score=None,
                tweet_text=None,
            )

        rollups = self._aggregate(records)
        top_tokens = self._select_top_tokens(rollups, max_tokens=max_tokens)
        await self._enrich_with_geckoterminal(top_tokens)
        await self._enrich_with_coingecko(top_tokens)
        tweet_text = self._render_tweet(
            generated_at,
            window_start,
            top_tokens,
            total_alerts=len(records),
            total_tokens=len(rollups),
            records=records,
        )

        return DailySummaryResult(
            generated_at=generated_at,
            window_start=window_start,
            token_rollups=top_tokens,
            total_alerts=len(records),
            total_tokens=len(rollups),
            median_score=_calculate_median([r.get("momentum_score") for r in records]),
            tweet_text=tweet_text,
        )

    def _aggregate(self, records: List[Dict[str, Any]]) -> Dict[str, TokenRollup]:
        rollups: Dict[str, TokenRollup] = {}
        for record in records:
            symbol = record.get("token") or record.get("pair_name") or "?"
            symbol = str(symbol).upper()
            payload: Dict[str, Any] = record.get("raw_payload") or {}
            net_profit = float(record.get("net_profit_usd") or 0.0)
            score = float(record.get("momentum_score") or 0.0)

            rollup = rollups.setdefault(symbol, TokenRollup(symbol=symbol))
            rollup.record(payload, score, net_profit)
        return rollups

    def _select_top_tokens(self, rollups: Dict[str, TokenRollup], *, max_tokens: int) -> List[TokenRollup]:
        ordered = sorted(
            rollups.values(),
            key=lambda r: (
                -(r.max_score),
                -r.alerts,
                -r.effective_volume,
            ),
        )
        return ordered[:max_tokens]

    async def _enrich_with_geckoterminal(self, rollups: List[TokenRollup]) -> None:
        coroutine_indices: List[int] = []
        coroutines: List[Any] = []
        for idx, rollup in enumerate(rollups):
            if not rollup.base_token_address:
                continue
            coroutine_indices.append(idx)
            coroutines.append(self._gecko.get_token_metrics(self._network, rollup.base_token_address))

        results: List[Any] = []
        if coroutines:
            results = await asyncio.gather(*coroutines, return_exceptions=True)

        for idx, result in zip(coroutine_indices, results):
            metrics = result if isinstance(result, dict) else {}
            rollups[idx].gecko_metrics = metrics

        # ensure others have default dict
        for rollup in rollups:
            if not rollup.gecko_metrics:
                rollup.gecko_metrics = {}

    async def _enrich_with_coingecko(self, rollups: List[TokenRollup]) -> None:
        for rollup in rollups:
            coin_id = rollup.coingecko_id
            if not coin_id:
                continue
            try:
                data = await self._coingecko.get_coin_by_id(coin_id)
            except Exception:
                data = None
            if not data:
                continue
            market = data.get("market_data", {}) if isinstance(data, dict) else {}
            current_price = _safe_float((market.get("current_price") or {}).get("usd"))
            price_change_pct = _safe_float(market.get("price_change_percentage_24h"))
            rollup.coingecko_market = {
                "price_usd": current_price,
                "price_change_pct_24h": price_change_pct,
            }

    def _render_tweet(
        self,
        generated_at: datetime,
        window_start: datetime,
        top_tokens: List[TokenRollup],
        *,
        total_alerts: int,
        total_tokens: int,
        records: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not top_tokens:
            return None

        header = f"Base daily pulse • {generated_at.strftime('%d %b %H:%M')} UTC"
        scores = [float(r.get("momentum_score") or 0.0) for r in records]
        median_score_value = _calculate_median(scores)
        summary_line = (
            f"Alerts: {total_alerts} | Tokens: {total_tokens} | Median score: {median_score_value:.1f}"
            if median_score_value is not None
            else f"Alerts: {total_alerts} | Tokens: {total_tokens}"
        )

        token_lines: List[str] = []
        for rollup in top_tokens:
            volume = _format_usd((rollup.gecko_metrics or {}).get("volume_usd_24h"))
            liquidity = _format_usd((rollup.gecko_metrics or {}).get("total_liquidity_usd"))
            price_change = _format_pct((rollup.coingecko_market or {}).get("price_change_pct_24h"))
            trend_label = {
                "buy": "↑ flow",
                "sell": "↓ flow",
                "flat": "↔ flow",
            }[rollup.momentum_skew]
            token_lines.append(
                f"${rollup.symbol}: max {rollup.max_score:.1f} ({rollup.alerts}) {trend_label} • Vol {volume} • Liq {liquidity} • Δ {price_change}"
            )

        footer = "#Base #DeFi"
        tweet = "\n".join([header, summary_line, *token_lines, footer])

        if len(tweet) > 275:
            # Trim by dropping liquidity details first, then price change if still too long.
            token_lines_compact: List[str] = []
            for rollup in top_tokens:
                volume = _format_usd((rollup.gecko_metrics or {}).get("volume_usd_24h"))
                price_change = _format_pct((rollup.coingecko_market or {}).get("price_change_pct_24h"))
                token_lines_compact.append(
                    f"${rollup.symbol}: max {rollup.max_score:.1f} ({rollup.alerts}) • Vol {volume} • Δ {price_change}"
                )
            tweet = "\n".join([header, summary_line, *token_lines_compact, footer])

        if len(tweet) > 280:
            # Final resort: truncate token lines to keep within limit.
            trimmed = []
            for line in token_lines[:2]:
                trimmed.append(line[:120])
            tweet = "\n".join([header, summary_line, *trimmed, footer])[:280]

        return tweet


def _calculate_median(values: List[Optional[float]]) -> Optional[float]:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return median(clean)


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_usd(value: Optional[float]) -> str:
    if value is None or value <= 0:
        return "n/a"
    if value >= 1_000_000_000:
        return f"${value/1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value/1_000:.1f}K"
    return f"${value:.0f}"


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}%"


__all__ = [
    "BaseDailySummaryBuilder",
    "DailySummaryResult",
    "TokenRollup",
]
