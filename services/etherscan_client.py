#!/usr/bin/env python3
import asyncio
import time
from typing import Optional, Dict

import aiohttp
from constants import C_RED, C_RESET, ETHERSCAN_API_BASE_URL

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

class EtherscanClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key
        self._last_request_time = 0.0
        self._rate_limit_delay = 0.2 # Etherscan has a 5 calls/sec rate limit (200ms delay)

    async def _wait_for_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    async def get_gas_price_in_gwei(self, chain_name: str, chain_info: dict) -> Optional[float]:
        """
        Gets the current 'standard' gas price in Gwei.
        Uses Blockscout for Base chain and Etherscan for all others.
        """
        await self._wait_for_rate_limit()

        # --- Base Chain: Use Blockscout API ---
        if chain_name == 'base':
            url = "https://base.blockscout.com/api/v1/gas-price-oracle"
            data = await api_get(url, self.session)
            if data and 'average' in data:
                try:
                    # Blockscout returns Gwei directly
                    return float(data['average'])
                except (ValueError, TypeError):
                    pass
            log_error(f"Could not parse gas price from Blockscout for {chain_name}: {data if data else 'No data'}")
            return None

        # --- Other Chains: Use Etherscan API ---
        chain_id = chain_info.get('chainId')
        if not chain_id:
            log_error(f"Chain ID not configured for chain: {chain_name}")
            return None

        url = f"{ETHERSCAN_API_BASE_URL}?module=gastracker&action=gasoracle&apikey={self.api_key}&chainid={chain_id}"
        data = await api_get(url, self.session)
        if data and data.get('status') == '1' and data.get('result'):
            # ProposeGasPrice is for EIP-1559 chains, SafeGasPrice is a fallback
            gas_price = data['result'].get('ProposeGasPrice') or data['result'].get('SafeGasPrice')
            try:
                return float(gas_price)
            except (ValueError, TypeError):
                pass
        
        log_error(f"Could not parse gas price from Etherscan for {chain_name}: {data if data else 'No data'}")
        return None

    async def get_token_info(self, token_address: str, chain_id: int) -> Optional[Dict]:
        """
        Gets token information (name, symbol, total supply) for a given contract address.
        """
        await self._wait_for_rate_limit()
        # Use the single ETHERSCAN_API_BASE_URL and always include chainid
        url = f"{ETHERSCAN_API_BASE_URL}?module=token&action=tokeninfo&contractaddress={token_address}&apikey={self.api_key}&chainid={chain_id}"
        data = await api_get(url, self.session)
        if data and data.get('status') == '1' and data.get('result'):
            return data['result'][0]
        log_error(f"Could not retrieve token info for {token_address} on chain ID {chain_id}: {data.get('message', 'No message')}")
        return None
