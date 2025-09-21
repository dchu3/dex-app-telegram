#!/usr/bin/env python3
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TradingPair:
    """Represents a single trading pair on a DEX."""
    dex: str
    price: float
    liquidity: float
    pair_name: str

@dataclass
class ArbitrageOpportunity:
    """Represents a potential arbitrage opportunity."""
    pair_name: str
    chain_name: str
    direction: str  # 'BULLISH' or 'BEARISH'
    buy_dex: str
    buy_price: float
    sell_dex: str
    sell_price: float
    gross_diff_pct: float
    effective_volume: float
    gross_profit_usd: float
    gas_cost_usd: float
    dex_fee_cost: float
    slippage_cost: float
    net_profit_usd: float
    gas_price_gwei: float
    base_token_address: str # The address of the token being arbitraged
    buy_dex_volume_usd: float
    sell_dex_volume_usd: float
    dominant_is_buy_side: bool
    dominant_volume_ratio: float
    price_impact_pct: float
    buy_price_change_h1: Optional[float]
    sell_price_change_h1: Optional[float]
    short_term_volume_ratio: float
    short_term_txns_total: int
    is_early_momentum: bool
    buy_pair_address: Optional[str] = None
    sell_pair_address: Optional[str] = None
    quote_token_address: Optional[str] = None
    buy_token_address: Optional[str] = None
    sell_token_address: Optional[str] = None

@dataclass
class MultiLegArbitrageOpportunity:
    """Represents a potential multi-leg (e.g., triangular) arbitrage opportunity."""
    chain_name: str
    cycle_path: List[str]
    trade_volume_usd: float
    gross_profit_usd: float
    net_profit_usd: float
    gas_cost_usd: float
    num_swaps: int
