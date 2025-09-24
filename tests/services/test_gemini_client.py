import asyncio
from unittest.mock import AsyncMock

import pytest

from services.gemini_client import GeminiClient, GeminiAnalysis


class DummySession:
    async def post(self):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_generate_token_analysis_enforces_tweet_constraints(monkeypatch):
    session = DummySession()
    client = GeminiClient(session, api_key="fake")

    async def fake_post(url, session, json_data, headers=None):
        return {
            "candidates": [
                {"content": {"parts": [{"text": "https://bad-link.com this exceeds 280 characters by virtue of the repeated text " * 5}]}}
            ]
        }

    monkeypatch.setattr("services.gemini_client.api_post", fake_post)

    result = await client.generate_token_analysis({
        "direction": "BULLISH",
        "symbol": "BRETT",
        "chain": "Base",
        "profit_percentage": 1.5,
        "momentum_score": 6.2,
        "current_price": 1.23,
        "buy_dex": "Uniswap",
        "sell_dex": "Aerodrome",
        "buy_price": 1.22,
        "sell_price": 1.24,
        "net_profit_usd": 4.0,
        "effective_volume": 1000.0,
        "dominant_volume_ratio": 2.0,
        "dominant_flow_side": "sell",
        "is_early_momentum": True,
    })

    assert isinstance(result, GeminiAnalysis)
    assert "Momentum score" in result.telegram_detail
    assert len(result.twitter_summary) <= 280
    assert "http" not in result.twitter_summary.lower()


@pytest.mark.asyncio
async def test_generate_token_analysis_returns_sanitized_text(monkeypatch):
    session = DummySession()
    client = GeminiClient(session, api_key="fake")

    async def fake_post(url, session, json_data, headers=None):
        return {
            "candidates": [
                {"content": {"parts": [{"text": '{"telegram_detail": "Momentum score 6.2/10 reflects 3 detections with 2.0x flow and RSI 55. History shows 5.8 on 2024-01-01.", "twitter_summary": "BRETT Base: score 6.2/10; spread 1.50%; flow sell 2.00x; detections 3; RSI 55."}'}]}}
            ]
        }

    monkeypatch.setattr("services.gemini_client.api_post", fake_post)

    result = await client.generate_token_analysis({
        "direction": "BULLISH",
        "symbol": "BRETT",
        "chain": "Base",
        "profit_percentage": 1.5,
        "momentum_score": 6.2,
        "current_price": 1.23,
        "buy_dex": "Uniswap",
        "sell_dex": "Aerodrome",
        "buy_price": 1.22,
        "sell_price": 1.24,
        "net_profit_usd": 4.0,
        "effective_volume": 1000.0,
        "dominant_volume_ratio": 2.0,
        "dominant_flow_side": "sell",
        "is_early_momentum": False,
        "momentum_breakdown": {
            "volume_divergence": 2.0,
            "persistence_count": 3,
            "rsi_value": 55,
            "dominant_flow_side": "sell",
            "dominant_volume_ratio": 2.0,
        },
        "momentum_history": [
            {"timestamp_utc": "2024-01-01 12:00:00", "momentum_score": 5.8, "spread_pct": 1.3, "net_profit_usd": 3.5}
        ],
    })
    assert isinstance(result, GeminiAnalysis)
    assert "Momentum score" in result.telegram_detail
    assert len(result.twitter_summary) <= 280
    assert "BRETT" in result.twitter_summary
