#!/usr/bin/env python3
import asyncio
import time
from typing import Optional, Dict, List

import aiohttp
from constants import (DEXSCREENER_API_BASE_URL, C_RED, C_RESET)

def log_error(message: str) -> None:
    """Centralized error logging."""
    print(f"{C_RED}{message}{C_RESET}")

async def api_get(url: str, session: aiohttp.ClientSession, retries: int = 3, timeout: int = 30) -> Optional[Dict]:
    """Makes an async GET request with retries and timeout."""
    for attempt in range(retries):
        try:
            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            if attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                log_error(f"API request failed after {retries} attempts: {e}")
                return None

from services.coingecko_client import CoinGeckoClient


class DexScreenerClient:
    def __init__(self, session: aiohttp.ClientSession, coingecko_client: CoinGeckoClient):
        self.session = session
        self.coingecko_client = coingecko_client
        self._last_request_time = 0.0
        self._rate_limit_delay = 0.5 # 500ms delay between requests to stay under 300 req/min

    async def _wait_for_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    async def get_native_token_price_in_usd(self, chain_info: dict) -> Optional[float]:
        """Gets the current price of a chain's native token in USD."""
        await self._wait_for_rate_limit()
        url = f"{DEXSCREENER_API_BASE_URL}/pairs/{chain_info['dexscreenerName']}/{chain_info['nativeTokenPair']}"
        data = await api_get(url, self.session)
        if data and data.get('pair') and data['pair'].get('priceUsd'):
            try:
                return float(data['pair']['priceUsd'])
            except (ValueError, TypeError):
                pass
        
        # --- Fallback for Base chain ---
        if chain_info['dexscreenerName'] == 'base':
            return await self.coingecko_client.get_eth_price_in_usd()

        log_error(f"Could not parse native token price from API response for {chain_info['dexscreenerName']}.")
        return None

    async def search_dexscreener(self, token_symbol: str) -> Optional[Dict]:
        """Queries the DexScreener API for a given token symbol."""
        await self._wait_for_rate_limit()
        url = f"{DEXSCREENER_API_BASE_URL}/search?q={token_symbol}"
        return await api_get(url, self.session)

    async def get_pair_by_address(self, pair_address: str, chain_name: str) -> Optional[Dict]:
        """Gets information for a specific pair by its address."""
        await self._wait_for_rate_limit()
        url = f"{DEXSCREENER_API_BASE_URL}/pairs/{chain_name}/{pair_address}"
        data = await api_get(url, self.session)
        return data.get('pair') if data and 'pair' in data else None
