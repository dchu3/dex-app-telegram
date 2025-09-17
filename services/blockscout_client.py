#!/usr/bin/env python3
import asyncio
from typing import Optional, Dict

import aiohttp
from constants import C_RED, C_RESET

def log_error(message: str) -> None:
    """Centralized error logging."""
    print(f"{C_RED}{message}{C_RESET}")

async def api_get(url: str, session: aiohttp.ClientSession, retries: int = 3, timeout: int = 10) -> Optional[Dict]:
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

class BlockscoutClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_api_url = "https://base.blockscout.com/api/v2"

    async def get_contract_name(self, address: str) -> Optional[str]:
        """
        Gets the verified name of a contract from its address.
        Returns None if the contract is not verified or not found.
        """
        url = f"{self.base_api_url}/smart-contracts/{address}"
        data = await api_get(url, self.session)
        if data and data.get('name'):
            return data['name']
        return None
