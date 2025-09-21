"""Simple trade execution scaffolding for Aerodrome ↔ Uniswap opportunities."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from analysis.models import ArbitrageOpportunity

try:
    from web3 import Web3
    from web3.exceptions import Web3Exception
except Exception:  # pragma: no cover - web3 optional for tests
    Web3 = None
    Web3Exception = Exception

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    }
]


@dataclass(slots=True)
class TradeResult:
    opportunity_key: str
    executed: bool
    tx_hashes: list[str]
    reason: Optional[str] = None


class TradeExecutor:
    """Minimal execution harness; extend to submit real swaps."""

    def __init__(
        self,
        rpc_url: str,
        private_key: str,
        wallet_address: Optional[str],
        max_slippage_pct: float,
    ) -> None:
        if Web3 is None:
            raise RuntimeError("web3.py is required for --auto-trade runs.")

        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise RuntimeError(f"Could not connect to RPC URL: {rpc_url}")

        self.account = self.web3.eth.account.from_key(private_key)
        self.wallet_address = wallet_address or self.account.address
        self.max_slippage = Decimal(max_slippage_pct) / Decimal(100)
        self._decimals_cache: dict[str, int] = {}
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    async def execute(self, opportunity: ArbitrageOpportunity) -> TradeResult:
        return await asyncio.to_thread(self._execute_sync, opportunity)

    def _execute_sync(self, opportunity: ArbitrageOpportunity) -> TradeResult:
        try:
            opp_key = f"{opportunity.chain_name}-{opportunity.pair_name}-{opportunity.buy_dex}-{opportunity.sell_dex}"
            quote_address = opportunity.quote_token_address
            if not quote_address:
                return TradeResult(opportunity_key=opp_key, executed=False, reason="Missing quote token address")

            base_address = opportunity.buy_token_address or opportunity.base_token_address
            if not base_address:
                return TradeResult(opportunity_key=opp_key, executed=False, reason="Missing base token address")

            quote_decimals = self._get_token_decimals(quote_address)
            base_decimals = self._get_token_decimals(base_address)

            usd_volume = Decimal(str(opportunity.effective_volume))
            buy_price = Decimal(str(opportunity.buy_price))
            quote_amount = usd_volume
            base_amount = usd_volume / buy_price

            quote_amount_wei = self._to_wei(quote_amount, quote_decimals)
            base_amount_wei = self._to_wei(base_amount, base_decimals)

            self.logger.info(
                "[AutoTrade] %s | Buy %s on %s then sell on %s | quote=%s wei base=%s wei",
                opportunity.pair_name,
                base_address,
                opportunity.buy_dex,
                opportunity.sell_dex,
                quote_amount_wei,
                base_amount_wei,
            )

            # TODO: Add on-chain quoting + swap execution.
            return TradeResult(opportunity_key=opp_key, executed=False, reason="Trading logic not implemented yet")
        except Web3Exception as exc:  # pragma: no cover
            self.logger.error("Web3 error while preparing trade: %s", exc)
            return TradeResult(opportunity_key=opp_key, executed=False, reason=str(exc))
        except Exception as exc:  # pragma: no cover
            self.logger.error("Unexpected error while preparing trade: %s", exc)
            return TradeResult(opportunity_key=opp_key, executed=False, reason=str(exc))

    def _get_token_decimals(self, token_address: str) -> int:
        token_address = self.web3.to_checksum_address(token_address)
        if token_address not in self._decimals_cache:
            contract = self.web3.eth.contract(address=token_address, abi=ERC20_ABI)
            decimals = contract.functions.decimals().call()
            self._decimals_cache[token_address] = decimals
        return self._decimals_cache[token_address]

    @staticmethod
    def _to_wei(amount: Decimal, decimals: int) -> int:
        scale = Decimal(10) ** decimals
        return int((amount * scale).to_integral_value())

    async def close(self) -> None:
        return None
