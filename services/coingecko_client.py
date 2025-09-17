#!/usr/bin/env python3
import asyncio
import os
import time
from typing import Optional, Dict, List

import aiohttp
from constants import (COINGECKO_API_BASE_URL, COINGECKO_API_KEY_ENV_VAR, C_RED, C_RESET)
from momentum_indicator import calculate_rsi

def log_error(message: str) -> None:
    """Centralized error logging."""
    print(f"{C_RED}{message}{C_RESET}")

async def api_get(url: str, session: aiohttp.ClientSession, params: Optional[Dict] = None, headers: Optional[Dict] = None, retries: int = 3, timeout: int = 10) -> Optional[Dict]:
    """Makes an async GET request with retries and timeout."""
    for attempt in range(retries):
        try:
            async with session.get(url, params=params, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            if attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                log_error(f"API request failed after {retries} attempts: {e}")
                return None

class CoinGeckoClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: Optional[str] = None):
        self.session = session
        self.api_key = api_key
        self.headers = {'x-cg-demo-api-key': self.api_key} if self.api_key else {}
        self._last_request_time = 0.0
        self._rate_limit_delay = 6

    async def _wait_for_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    async def get_trending_coins(self) -> Optional[List[Dict]]:
        await self._wait_for_rate_limit()
        url = f"{COINGECKO_API_BASE_URL}/search/trending"
        data = await api_get(url, self.session, headers=self.headers)
        if data and 'coins' in data:
            return data['coins'][:7]
        log_error("Could not parse trending coins from CoinGecko API response.")
        return None

    async def search_coin(self, query: str) -> Optional[Dict]:
        await self._wait_for_rate_limit()
        url = f"{COINGECKO_API_BASE_URL}/search"
        params = {'query': query}
        data = await api_get(url, self.session, params=params, headers=self.headers)
        if data and data.get('coins'):
            return data['coins'][0]
        log_error(f"Could not find coin '{query}' on CoinGecko.")
        return None

    async def get_coin_by_id(self, coin_id: str) -> Optional[Dict]:
        await self._wait_for_rate_limit()
        url = f"{COINGECKO_API_BASE_URL}/coins/{coin_id}"
        params = {
            'localization': 'false', 'tickers': 'false', 'market_data': 'true',
            'community_data': 'false', 'developer_data': 'false', 'sparkline': 'false'
        }
        return await api_get(url, self.session, params=params, headers=self.headers)

    async def get_price(self, coin_ids: List[str], vs_currencies: List[str]) -> Optional[Dict]:
        await self._wait_for_rate_limit()
        url = f"{COINGECKO_API_BASE_URL}/simple/price"
        params = {'ids': ",".join(coin_ids), 'vs_currencies': ",".join(vs_currencies)}
        return await api_get(url, self.session, params=params, headers=self.headers)

    async def get_global_market_data(self) -> Optional[Dict]:
        await self._wait_for_rate_limit()
        url = f"{COINGECKO_API_BASE_URL}/global"
        return await api_get(url, self.session, headers=self.headers)

    async def get_eth_price_in_usd(self) -> Optional[float]:
        prices = await self.get_price(coin_ids=['ethereum'], vs_currencies=['usd'])
        if prices and 'ethereum' in prices and 'usd' in prices['ethereum']:
            return prices['ethereum']['usd']
        log_error("Could not parse ETH price from CoinGecko API response.")
        return None

    async def get_rsi(self, coin_id: str, days: int = 15) -> Optional[float]:
        await self._wait_for_rate_limit()
        url = f"{COINGECKO_API_BASE_URL}/coins/{coin_id}/market_chart"
        params = {'vs_currency': 'usd', 'days': str(days), 'interval': 'daily'}
        chart_data = await api_get(url, self.session, params=params, headers=self.headers)

        if not chart_data or 'prices' not in chart_data or len(chart_data['prices']) < 15:
            log_error(f"Not enough market chart data to calculate RSI for '{coin_id}'.")
            return None

        closing_prices = [item[1] for item in chart_data['prices']]
        rsi_value = calculate_rsi(closing_prices)
        return rsi_value

async def main():
    try:
        async with aiohttp.ClientSession() as session:
            api_key = os.environ.get(COINGECKO_API_KEY_ENV_VAR)
            client = CoinGeckoClient(session, api_key=api_key)

            print("--- Testing get_trending_coins ---")
            trending_coins = await client.get_trending_coins()
            if trending_coins:
                print("Trending coins found:")
                for coin in trending_coins:
                    print(f"- {coin['item']['name']} ({coin['item']['symbol']})")
            
            print("\n--- Testing search_coin ---")
            coin_info = await client.search_coin("bitcoin")
            if coin_info:
                print(f"Found coin: {coin_info['name']} with ID: {coin_info['id']}")

            print("\n--- Testing get_eth_price_in_usd ---")
            eth_price = await client.get_eth_price_in_usd()
            if eth_price:
                print(f"Current ETH price: ${eth_price:,.2f}")

            print("\n--- Testing get_rsi for Bitcoin ---")
            btc_rsi = await client.get_rsi("bitcoin")
            if btc_rsi is not None:
                print(f"Current Bitcoin 14-day RSI: {btc_rsi:.2f}")
            else:
                print("Could not calculate RSI for Bitcoin.")
    except Exception as e:
        log_error(f"An unexpected error occurred in main: {e}")

if __name__ == "__main__":
    print("--- Executing CoinGecko Client Examples ---")
    asyncio.run(main())