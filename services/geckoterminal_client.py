#!/usr/bin/env python3
"""Client helpers for GeckoTerminal REST API (used via MCP)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import aiohttp

from constants import C_RED, C_RESET


def _log_error(message: str) -> None:
    print(f"{C_RED}{message}{C_RESET}")


class GeckoTerminalClient:
    """Thin async wrapper for GeckoTerminal public endpoints."""

    BASE_URL = "https://api.geckoterminal.com/api/v2"

    def __init__(self, session: aiohttp.ClientSession, *, rate_limit_delay: float = 1.0) -> None:
        self._session = session
        self._rate_limit_delay = rate_limit_delay
        self._last_request_ts: float = 0.0
        self._lock = asyncio.Lock()

    async def _wait_for_rate_limit(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_ts
            if elapsed < self._rate_limit_delay:
                await asyncio.sleep(self._rate_limit_delay - elapsed)
            self._last_request_ts = asyncio.get_event_loop().time()

    async def _get(self, path: str, *, params: Optional[Dict[str, Any]] = None, retries: int = 3, timeout: int = 10) -> Optional[Dict[str, Any]]:
        await self._wait_for_rate_limit()
        url = f"{self.BASE_URL}{path}"
        for attempt in range(retries):
            try:
                async with self._session.get(url, params=params, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as exc:
                if attempt < retries - 1:
                    await asyncio.sleep(1.5)
                    continue
                _log_error(f"GeckoTerminal request failed for {url}: {exc}")
                return None
        return None

    async def get_token_overview(self, network: str, token_address: str) -> Optional[Dict[str, Any]]:
        """Return the token overview payload (volume, liquidity, price changes)."""
        token_address = token_address.lower()
        data = await self._get(f"/networks/{network}/tokens/{token_address}")
        if not data:
            return None
        return data.get("data")

    async def get_token_metrics(self, network: str, token_address: str) -> Optional[Dict[str, Optional[float]]]:
        """Convenience helper to extract common metrics for a token on a network."""
        overview = await self.get_token_overview(network, token_address)
        if not overview:
            return None
        attrs = overview.get("attributes", {})

        def _extract(container: Dict[str, Any], *keys: str) -> Optional[float]:
            current: Any = container
            for key in keys:
                if not isinstance(current, dict):
                    return None
                current = current.get(key)
            if current is None:
                return None
            try:
                return float(current)
            except (TypeError, ValueError):
                return None

        return {
            "symbol": attrs.get("symbol"),
            "name": attrs.get("name"),
            "price_usd": _extract(attrs, "price_usd"),
            "volume_usd_24h": _extract(attrs, "volume_usd", "h24"),
            "volume_usd_6h": _extract(attrs, "volume_usd", "h6"),
            "volume_usd_1h": _extract(attrs, "volume_usd", "h1"),
            "total_liquidity_usd": _extract(attrs, "total_reserve_in_usd"),
            "price_change_pct_24h": _extract(attrs, "price_change_percentage", "h24"),
            "price_change_pct_6h": _extract(attrs, "price_change_percentage", "h6"),
        }
