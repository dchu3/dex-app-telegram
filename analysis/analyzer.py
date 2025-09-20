#!/usr/bin/env python3
from collections import defaultdict
from typing import List, Dict

from analysis.models import ArbitrageOpportunity, TradingPair
from config import AppConfig
from constants import GAS_UNITS_PER_SWAP

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
        """
        Analyzes API data to find arbitrage opportunities and returns them as a list.
        """
        prices_by_pair: Dict[str, List[Dict]] = defaultdict(list)
        opportunities = []

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
            h1_buys = txns_h1.get('buys', 0)
            h1_sells = txns_h1.get('sells', 0)

            # --- Data Quality Filters ---
            if liq_usd < self.config.min_liquidity:
                continue
            if vol_24h < self.config.min_volume:
                continue
            # Transaction Filter: Ensure a minimum number of hourly transactions (if enabled)
            if self.config.min_txns_h1 > 0 and (h1_buys + h1_sells) < self.config.min_txns_h1:
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
                'base_token_address': base_token_address,
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

                    buy_option = lower_option
                    sell_option = higher_option

                    gross_diff = sell_option['price'] - buy_option['price']
                    if gross_diff <= 0:
                        continue

                    profit_percentage = (gross_diff / buy_option['price']) * 100

                    if direction == 'BEARISH' and profit_percentage < self.config.min_bearish_discrepancy:
                        continue

                    effective_volume = min(
                        self.config.trade_volume,
                        buy_option['liquidity'] * 0.005,
                        sell_option['liquidity'] * 0.005
                    )
                    if effective_volume < 1.0:
                        continue

                    slippage_cost = effective_volume * (self.config.slippage / 100.0)
                    dex_fee_cost = (effective_volume * 2) * (self.config.dex_fee / 100.0)
                    gas_units = GAS_UNITS_PER_SWAP[chain_name]
                    gas_cost_native = (gas_price_gwei * 1e-9) * gas_units * 2
                    gas_cost_usd = gas_cost_native * native_price_usd
                    gross_profit_usd = (gross_diff / buy_option['price']) * effective_volume
                    net_profit_usd = gross_profit_usd - gas_cost_usd - dex_fee_cost - slippage_cost

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
                    ))


        return opportunities

