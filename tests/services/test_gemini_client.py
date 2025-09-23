import asyncio
from unittest.mock import AsyncMock

import pytest

from services.gemini_client import GeminiClient


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

    expected = "Momentum snapshot: BRETT on Base | spread 1.50% | score 6.2/10 | Uniswap -> Aerodrome | est net $4.00 on $1,000 | sell-side flow 2.00x | early momentum cue"
    assert result == expected
    assert len(result) <= 280
    assert "http" not in result.lower()


@pytest.mark.asyncio
async def test_generate_token_analysis_returns_sanitized_text(monkeypatch):
    session = DummySession()
    client = GeminiClient(session, api_key="fake")

    async def fake_post(url, session, json_data, headers=None):
        return {
            "candidates": [
                {"content": {"parts": [{"text": "BRETT on Base shows 1.5% spread, score 6.2/10 via Uniswap -> Aerodrome. 📈"}]}}
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
    })

    assert result == "BRETT on Base shows 1.5% spread, score 6.2/10 via Uniswap -> Aerodrome. 📈"
