#!/usr/bin/env python3
import math
from collections import defaultdict
from typing import Dict, List

from analysis.models import ArbitrageOpportunity, TradingPair
from config import AppConfig
from constants import (
    GAS_UNITS_PER_SWAP,
    EARLY_MOMENTUM_MIN_LIQUIDITY,
    EARLY_MOMENTUM_MIN_VOLUME,
    EARLY_MOMENTUM_MIN_VOLUME_M5,
    EARLY_MOMENTUM_MIN_TXNS_M5,
    EARLY_MOMENTUM_VOLUME_RATIO_THRESHOLD,
)


class OpportunityAnalyzer:
    def __init__(self, config: AppConfig):
        self.config = config

    def find_opportunities(
        self,
        pairs_data: Dict,
        target_token: str,
        native_price_usd: float,
        gas_price_gwei: float,
        chain_name: str,
    ) -> List[ArbitrageOpportunity]:
        """Analyzes API data to find arbitrage opportunities and returns them as a list."""
        prices_by_pair: Dict[str, List[Dict]] = defaultdict(list)
        opportunities: List[ArbitrageOpportunity] = []

        if not pairs_data or 'pairs' not in pairs_data or not pairs_data['pairs']:
            return []

        target_lower = target_token.lower()
        for pair in pairs_data['pairs']:
            if pair.get('chainId') != chain_name:
                continue

            liq_usd = pair.get('liquidity', {}).get('usd', 0.0)
            vol_24h = pair.get('volume', {}).get('h24', 0.0)
            vol_m5 = pair.get('volume', {}).get('m5', 0.0)
            txns_h1 = pair.get('txns', {}).get('h1', {})
            h1_total_txns = txns_h1.get('buys', 0) + txns_h1.get('sells', 0)
            txns_m5 = pair.get('txns', {}).get('m5', {})
            txns_m5_total = txns_m5.get('buys', 0) + txns_m5.get('sells', 0)

            liquidity_ok = liq_usd >= self.config.min_liquidity
            volume_ok = vol_24h >= self.config.min_volume
            txns_ok = self.config.min_txns_h1 == 0 or h1_total_txns >= self.config.min_txns_h1

            is_early_momentum = False
            if not (liquidity_ok and volume_ok and txns_ok):
                is_early_momentum = self._is_early_momentum_candidate(
                    liquidity=liq_usd,
                    volume_24h=vol_24h,
                    volume_m5=vol_m5,
                    txns_m5=txns_m5_total,
                )
                if not is_early_momentum:
                    continue
            elif not txns_ok:
                continue

            if not all(k in pair for k in ['dexId', 'baseToken', 'quoteToken', 'priceUsd', 'priceNative']):
                continue

            base_sym = pair['baseToken']['symbol'].lower()
            quote_sym = pair['quoteToken']['symbol'].lower()

            try:
                base_price_usd = float(pair['priceUsd'])
                price_native = float(pair['priceNative'])
            except (ValueError, TypeError):
                continue

            if base_sym == target_lower:
                target_price_usd = base_price_usd
                pair_name = f"{pair['baseToken']['symbol']}/{pair['quoteToken']['symbol']}"
                base_token_address = pair['baseToken']['address']
            elif quote_sym == target_lower:
                if price_native == 0:
                    continue
                target_price_usd = base_price_usd / price_native
                pair_name = f"{pair['baseToken']['symbol']}/{pair['quoteToken']['symbol']}"
                base_token_address = pair['quoteToken']['address']
            else:
                continue

            prices_by_pair[pair_name].append({
                'dex': pair['dexId'],
                'price': target_price_usd,
                'liquidity': liq_usd,
                'volume_24h': vol_24h,
                'volume_m5': vol_m5,
                'txns_m5_total': txns_m5_total,
                'base_token_address': base_token_address,
                'price_change_h1': pair.get('priceChange', {}).get('h1'),
                'is_early_momentum': is_early_momentum,
            })

        for pair_name, prices in sorted(prices_by_pair.items()):
            if len(prices) < 2:
                continue

            for i in range(len(prices)):
                for j in range(i + 1, len(prices)):
                    dex_a = prices[i]
                    dex_b = prices[j]

                    if dex_a['dex'] == dex_b['dex']:
                        continue
                    if dex_a['price'] <= 0 or dex_b['price'] <= 0:
                        continue
                    if dex_a['price'] == dex_b['price']:
                        continue

                    lower_option = dex_a if dex_a['price'] < dex_b['price'] else dex_b
                    higher_option = dex_b if lower_option is dex_a else dex_a

                    if dex_a['volume_24h'] == dex_b['volume_24h']:
                        dominant_option = lower_option
                    else:
                        dominant_option = dex_a if dex_a['volume_24h'] > dex_b['volume_24h'] else dex_b

                    dominant_is_buy_side = dominant_option is lower_option
                    direction = 'BULLISH' if dominant_is_buy_side else 'BEARISH'
                    other_option = higher_option if dominant_option is lower_option else lower_option
                    dominant_volume_ratio = 0.0
                    try:
                        dominant_volume_ratio = dominant_option['volume_24h'] / other_option['volume_24h'] if other_option['volume_24h'] > 0 else float('inf')
                    except (KeyError, TypeError, ZeroDivisionError):
                        dominant_volume_ratio = 0.0

                    buy_option = lower_option
                    sell_option = higher_option

                    gross_diff = sell_option['price'] - buy_option['price']
                    if gross_diff <= 0:
                        continue

                    profit_percentage = (gross_diff / buy_option['price']) * 100

                    if direction == 'BEARISH' and profit_percentage < self.config.min_bearish_discrepancy:
                        continue
                    if direction == 'BEARISH' and dominant_volume_ratio < 1.2:
                        continue

                    opportunity_is_early = buy_option.get('is_early_momentum') or sell_option.get('is_early_momentum')

                    effective_volume = min(
                        self.config.trade_volume,
                        buy_option['liquidity'] * 0.005,
                        sell_option['liquidity'] * 0.005,
                    )
                    if opportunity_is_early:
                        effective_volume = min(effective_volume, min(buy_option['liquidity'], sell_option['liquidity']) * 0.002)
                    if effective_volume < 1.0:
                        continue

                    slippage_cost = effective_volume * (self.config.slippage / 100.0)
                    buy_price_impact_pct = (effective_volume / buy_option['liquidity']) * 100 if buy_option['liquidity'] > 0 else float('inf')
                    sell_price_impact_pct = (effective_volume / sell_option['liquidity']) * 100 if sell_option['liquidity'] > 0 else float('inf')
                    price_impact_pct = buy_price_impact_pct + sell_price_impact_pct
                    impact_threshold = 2.0 if opportunity_is_early else 1.5
                    if math.isinf(price_impact_pct) or price_impact_pct > impact_threshold:
                        continue
                    price_impact_cost = effective_volume * (price_impact_pct / 100.0)

                    dex_fee_cost = (effective_volume * 2) * (self.config.dex_fee / 100.0)
                    gas_units = GAS_UNITS_PER_SWAP[chain_name]
                    gas_cost_native = (gas_price_gwei * 1e-9) * gas_units * 2
                    gas_cost_usd = gas_cost_native * native_price_usd
                    gross_profit_usd = (gross_diff / buy_option['price']) * effective_volume
                    net_profit_usd = gross_profit_usd - gas_cost_usd - dex_fee_cost - slippage_cost - price_impact_cost

                    if net_profit_usd <= 0:
                        continue

                    if direction == 'BULLISH' and profit_percentage < self.config.min_bullish_profit:
                        continue

                    opportunities.append(ArbitrageOpportunity(
                        pair_name=pair_name,
                        chain_name=chain_name,
                        direction=direction,
                        buy_dex=buy_option['dex'],
                        buy_price=buy_option['price'],
                        sell_dex=sell_option['dex'],
                        sell_price=sell_option['price'],
                        gross_diff_pct=profit_percentage,
                        effective_volume=effective_volume,
                        gross_profit_usd=gross_profit_usd,
                        gas_cost_usd=gas_cost_usd,
                        dex_fee_cost=dex_fee_cost,
                        slippage_cost=slippage_cost,
                        net_profit_usd=net_profit_usd,
                        gas_price_gwei=gas_price_gwei,
                        base_token_address=buy_option['base_token_address'],
                        buy_dex_volume_usd=buy_option['volume_24h'],
                        sell_dex_volume_usd=sell_option['volume_24h'],
                        dominant_is_buy_side=dominant_is_buy_side,
                        dominant_volume_ratio=dominant_volume_ratio,
                        price_impact_pct=price_impact_pct,
                        buy_price_change_h1=buy_option.get('price_change_h1'),
                        sell_price_change_h1=sell_option.get('price_change_h1'),
                        short_term_volume_ratio=self._calculate_short_term_volume_ratio(buy_option, sell_option),
                        short_term_txns_total=buy_option.get('txns_m5_total', 0) + sell_option.get('txns_m5_total', 0),
                        is_early_momentum=bool(opportunity_is_early),
                    ))

        return opportunities

    def _is_early_momentum_candidate(
        self,
        *,
        liquidity: float,
        volume_24h: float,
        volume_m5: float,
        txns_m5: int,
    ) -> bool:
        if liquidity < EARLY_MOMENTUM_MIN_LIQUIDITY:
            return False
        if volume_24h < EARLY_MOMENTUM_MIN_VOLUME:
            return False
        if volume_m5 < EARLY_MOMENTUM_MIN_VOLUME_M5:
            return False
        if txns_m5 < EARLY_MOMENTUM_MIN_TXNS_M5:
            return False
        if volume_24h <= 0:
            return False
        volume_ratio = volume_m5 / volume_24h
        return volume_ratio >= EARLY_MOMENTUM_VOLUME_RATIO_THRESHOLD

    @staticmethod
    def _calculate_short_term_volume_ratio(buy_option: Dict, sell_option: Dict) -> float:
        vol_m5_total = buy_option.get('volume_m5', 0.0) + sell_option.get('volume_m5', 0.0)
        vol_h24_total = buy_option.get('volume_24h', 0.0) + sell_option.get('volume_24h', 0.0)
        if vol_h24_total <= 0:
            return 0.0
        return min(vol_m5_total / vol_h24_total, 1.0)


# TradingPair model utilisation (not heavily used yet)
def build_trading_pair(dex: str, price: float, liquidity: float, pair_name: str) -> TradingPair:
    return TradingPair(dex=dex, price=price, liquidity=liquidity, pair_name=pair_name)
