#!/usr/bin/env python3
import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from aiohttp import ClientSession


@dataclass
class PairValidationResult:
    """Outcome of validating a single pool price against on-chain reserves."""
    validated: bool
    passed: bool
    price_usd: Optional[float]
    diff_pct: Optional[float]
    block_number: Optional[int]
    error: Optional[str] = None


class OnChainPriceValidator:
    """Queries an MCP-compatible JSON-RPC endpoint to validate pool pricing."""

    _TOKEN0_SIG = "0x0dfe1681"
    _TOKEN1_SIG = "0xd21220a7"
    _GET_RESERVES_SIG = "0x0902f1ac"
    _DECIMALS_SIG = "0x313ce567"

    def __init__(
        self,
        session: ClientSession,
        *,
        rpc_url: str,
        max_pct_diff: float,
        timeout: float,
        common_token_addresses: Dict[str, Dict[str, str]],
        block_cache_ttl: float = 1.0,
    ) -> None:
        self._session = session
        self._rpc_url = rpc_url
        self._max_pct_diff = max_pct_diff
        self._timeout = timeout
        self._common_token_addresses = common_token_addresses
        self._decimals_cache: Dict[str, int] = {}
        self._reserve_cache: Dict[str, Tuple[int, int, int]] = {}
        self._block_cache: Optional[Tuple[int, float]] = None
        self._block_cache_ttl = block_cache_ttl
        self._id_lock = asyncio.Lock()
        self._next_request_id = 1

    async def validate_pair_price(
        self,
        *,
        chain_name: str,
        pair_address: Optional[str],
        target_token_address: Optional[str],
        counter_token_address: Optional[str],
        dex_price_usd: float,
        native_price_usd: Optional[float],
    ) -> PairValidationResult:
        if not pair_address or not target_token_address:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=None,
                error="missing_pair_metadata",
            )

        pair_address = self._normalise_address(pair_address)
        target_token_address = self._normalise_address(target_token_address)

        try:
            block_number = await self._get_latest_block_number()
        except Exception as exc:  # pragma: no cover - defensive
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=None,
                error=f"block_number_error:{exc}",
            )

        try:
            token0, token1 = await self._get_pair_tokens(pair_address)
        except Exception as exc:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=block_number,
                error=f"token_resolution_error:{exc}",
            )

        if token0 is None or token1 is None:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=block_number,
                error="token_resolution_missing",
            )

        target_is_token0: Optional[bool]
        if target_token_address == token0:
            target_is_token0 = True
        elif target_token_address == token1:
            target_is_token0 = False
        else:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=block_number,
                error="target_not_in_pair",
            )

        counter_token = token1 if target_is_token0 else token0
        if counter_token_address:
            counter_token_address = self._normalise_address(counter_token_address)
            if counter_token_address != counter_token:
                counter_token = counter_token_address
        else:
            counter_token_address = counter_token

        try:
            reserves = await self._get_reserves(pair_address, block_number)
        except Exception as exc:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=block_number,
                error=f"reserve_fetch_error:{exc}",
            )

        reserve_target = reserves[0] if target_is_token0 else reserves[1]
        reserve_counter = reserves[1] if target_is_token0 else reserves[0]

        if reserve_target == 0 or reserve_counter == 0:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=block_number,
                error="empty_reserves",
            )

        try:
            target_decimals = await self._get_decimals(target_token_address)
            counter_decimals = await self._get_decimals(counter_token)
        except Exception as exc:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=block_number,
                error=f"decimals_error:{exc}",
            )

        reserve_target_float = reserve_target / (10 ** target_decimals)
        reserve_counter_float = reserve_counter / (10 ** counter_decimals)
        if reserve_target_float <= 0:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=block_number,
                error="invalid_reserve_ratio",
            )

        price_in_counter = reserve_counter_float / reserve_target_float
        usd_price = self._counter_to_usd(
            chain_name,
            counter_token,
            price_in_counter,
            native_price_usd,
        )
        if usd_price is None:
            return PairValidationResult(
                validated=False,
                passed=False,
                price_usd=None,
                diff_pct=None,
                block_number=block_number,
                error="unsupported_quote_token",
            )

        diff_pct: Optional[float] = None
        passed = False
        if dex_price_usd > 0:
            diff_pct = abs(usd_price - dex_price_usd) / dex_price_usd * 100
            passed = diff_pct <= self._max_pct_diff

        return PairValidationResult(
            validated=True,
            passed=passed,
            price_usd=usd_price,
            diff_pct=diff_pct,
            block_number=block_number,
            error=None if passed else ("price_mismatch" if diff_pct is not None else None),
        )

    async def _get_latest_block_number(self) -> int:
        now = time.monotonic()
        if self._block_cache and now - self._block_cache[1] <= self._block_cache_ttl:
            return self._block_cache[0]
        result = await self._rpc_call("eth_blockNumber", [])
        block_number = int(result, 16)
        self._block_cache = (block_number, now)
        return block_number

    async def _get_pair_tokens(self, pair_address: str) -> Tuple[Optional[str], Optional[str]]:
        cache_key = f"tokens:{pair_address}"
        if cache_key in self._reserve_cache:
            cached = self._reserve_cache[cache_key]
            return cached[0], cached[1]
        token0_hex = await self._eth_call(pair_address, self._TOKEN0_SIG)
        token1_hex = await self._eth_call(pair_address, self._TOKEN1_SIG)
        token0 = self._decode_address(token0_hex)
        token1 = self._decode_address(token1_hex)
        self._reserve_cache[cache_key] = (token0, token1, 0)
        return token0, token1

    async def _get_reserves(self, pair_address: str, block_number: int) -> Tuple[int, int, int]:
        cache_key = f"reserves:{pair_address}:{block_number}"
        cached = self._reserve_cache.get(cache_key)
        if cached:
            return cached
        block_hex = hex(block_number)
        result = await self._eth_call(pair_address, self._GET_RESERVES_SIG, block_hex)
        if not result or len(result) < 2:
            raise ValueError("empty_result")
        reserve0 = int(result[2:66], 16)
        reserve1 = int(result[66:130], 16)
        timestamp_last = int(result[130:194], 16)
        decoded = (reserve0, reserve1, timestamp_last)
        self._reserve_cache[cache_key] = decoded
        return decoded

    async def _get_decimals(self, token_address: str) -> int:
        token_address = self._normalise_address(token_address)
        cached = self._decimals_cache.get(token_address)
        if cached is not None:
            return cached
        result = await self._eth_call(token_address, self._DECIMALS_SIG)
        if result is None:
            raise ValueError("empty_result")
        decimals = int(result, 16)
        self._decimals_cache[token_address] = decimals
        return decimals

    async def _eth_call(self, to: str, data: str, block: str = "latest") -> Optional[str]:
        call_params = {"to": to, "data": data}
        return await self._rpc_call("eth_call", [call_params, block])

    async def _rpc_call(self, method: str, params: list) -> Optional[str]:
        request_id = await self._get_request_id()
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id,
        }
        async with self._session.post(self._rpc_url, json=payload, timeout=self._timeout) as response:
            response.raise_for_status()
            data = await response.json()
        if 'error' in data:
            raise RuntimeError(data['error'])
        return data.get('result')

    async def _get_request_id(self) -> int:
        async with self._id_lock:
            request_id = self._next_request_id
            self._next_request_id += 1
        return request_id

    def _counter_to_usd(
        self,
        chain_name: str,
        counter_token_address: str,
        price_in_counter: float,
        native_price_usd: Optional[float],
    ) -> Optional[float]:
        chain_tokens = self._common_token_addresses.get(chain_name, {})
        counter_lower = counter_token_address.lower()
        for stable_key in ("usdc", "usdt", "dai"):
            token_address = chain_tokens.get(stable_key)
            if token_address and counter_lower == token_address.lower():
                return price_in_counter
        native_candidates = (
            chain_tokens.get('weth'),
            chain_tokens.get('wmatic'),
            chain_tokens.get('wbnb'),
        )
        if native_price_usd is not None:
            for candidate in native_candidates:
                if candidate and counter_lower == candidate.lower():
                    return price_in_counter * native_price_usd
        return None

    @staticmethod
    def _normalise_address(address: str) -> str:
        if not address:
            return address
        if address.startswith('0x'):
            return '0x' + address[2:].lower()
        return '0x' + address.lower()

    @staticmethod
    def _decode_address(value: Optional[str]) -> Optional[str]:
        if not value or len(value) < 66:
            return None
        return '0x' + value[-40:]
