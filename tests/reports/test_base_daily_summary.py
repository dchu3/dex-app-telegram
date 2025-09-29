import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reports.base_daily_summary import BaseDailySummaryBuilder


class StubRepository:
    def __init__(self, records):
        self._records = records

    async def fetch_momentum_records(self, *, limit, token, direction, chain=None, since=None):
        return self._records


class StubGeckoTerminalClient:
    async def get_token_metrics(self, network: str, token_address: str):
        return {
            "volume_usd_24h": 1_500_000.0,
            "total_liquidity_usd": 3_200_000.0,
        }


class StubCoinGeckoClient:
    async def get_coin_by_id(self, coin_id: str):
        return {
            "market_data": {
                "current_price": {"usd": 1.23},
                "price_change_percentage_24h": 12.5,
            }
        }


@pytest.mark.asyncio
async def test_build_no_records_returns_empty_summary():
    repo = StubRepository([])
    builder = BaseDailySummaryBuilder(
        repository=repo,
        geckoterminal_client=StubGeckoTerminalClient(),
        coingecko_client=StubCoinGeckoClient(),
    )

    result = await builder.build()

    assert result.total_alerts == 0
    assert result.tweet_text is None
    assert not result.has_content


@pytest.mark.asyncio
async def test_build_compiles_summary_for_top_tokens():
    now = datetime.now(timezone.utc)
    records = [
        {
            "token": "AERO",
            "momentum_score": 7.4,
            "net_profit_usd": 120.0,
            "alert_time": now,
            "raw_payload": {
                "effective_volume_usd": 55_000.0,
                "dominant_flow_side": "buy",
                "base_token_address": "0xabc",
                "coingecko_id": "aerodrome-finance",
            },
        },
        {
            "token": "AERO",
            "momentum_score": 6.8,
            "net_profit_usd": 80.0,
            "alert_time": now - timedelta(hours=1),
            "raw_payload": {
                "effective_volume_usd": 24_000.0,
                "dominant_flow_side": "buy",
                "base_token_address": "0xabc",
                "coingecko_id": "aerodrome-finance",
            },
        },
        {
            "token": "DEGEN",
            "momentum_score": 6.1,
            "net_profit_usd": 50.0,
            "alert_time": now,
            "raw_payload": {
                "effective_volume_usd": 12_000.0,
                "dominant_flow_side": "sell",
                "base_token_address": "0xdef",
                "coingecko_id": "degen-base",
            },
        },
    ]
    repo = StubRepository(records)

    builder = BaseDailySummaryBuilder(
        repository=repo,
        geckoterminal_client=StubGeckoTerminalClient(),
        coingecko_client=StubCoinGeckoClient(),
    )

    result = await builder.build()

    assert result.total_alerts == len(records)
    assert result.total_tokens == 2
    assert result.has_content
    assert result.tweet_text is not None
    text = result.tweet_text
    assert "$AERO" in text
    assert "#Base" in text
