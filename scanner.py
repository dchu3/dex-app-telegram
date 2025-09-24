# scanner.py
import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple, Set, Optional

import aiohttp
from telegram.ext import Application

from analysis.analyzer import OpportunityAnalyzer
from analysis.models import ArbitrageOpportunity, MultiLegArbitrageOpportunity
from config import AppConfig
from constants import (
    CHAIN_CONFIG,
    C_BLUE,
    C_GREEN,
    C_RED,
    C_RESET,
    C_YELLOW,
    COMMON_TOKEN_ADDRESSES,
)
from services.dexscreener_client import DexScreenerClient
from services.etherscan_client import EtherscanClient
from services.coingecko_client import CoinGeckoClient
from services.gemini_client import GeminiClient
from services.twitter_client import TwitterClient
from services.trade_executor import TradeExecutor
from momentum_indicator import calculate_momentum_score
import analysis.multi_leg_analyzer as mla
from storage import SQLiteRepository

class ArbitrageScanner:
    def __init__(
        self,
        config: AppConfig,
        application: Application,
        dex_client: DexScreenerClient,
        etherscan_client: EtherscanClient,
        coingecko_client: CoinGeckoClient,
        blockscout_client: "BlockscoutClient",
        gemini_client: Optional["GeminiClient"],
        twitter_client: Optional["TwitterClient"],
        repository: Optional[SQLiteRepository] = None,
        trade_executor: Optional[TradeExecutor] = None,
    ):
        self.config = config
        self.application = application
        self.bot = application.bot
        self.dex_client = dex_client
        self.etherscan_client = etherscan_client
        self.coingecko_client = coingecko_client
        self.blockscout_client = blockscout_client
        self.gemini_client = gemini_client
        self.twitter_client = twitter_client
        self.dex_client.coingecko_client = coingecko_client
        self.alert_cache: Dict[str, float] = {}
        self.token_map: Dict[str, str] = {}
        self.opportunity_persistence: Dict[str, List[float]] = {}
        self._coin_id_cache: Dict[str, str] = {}
        self.repository = repository
        self.trade_executor = trade_executor
        self._current_scan_cycle_id: Optional[int] = None
        self._alerts_dispatched_in_cycle: int = 0

    async def start(self):
        """Initializes clients and starts the main scanning loop."""
        self.analyzer = OpportunityAnalyzer(self.config)
        await self._run_main_loop()

    async def _run_main_loop(self):
        """The main application loop."""
        while True:
            print("\n" + "="*50)
            print("Starting new arbitrage scan cycle...")
            try:
                await self._run_scan_cycle()
                self.application.bot_data['last_error'] = None
            except Exception as e:
                print(f"{C_RED}Error during scan cycle: {e}{C_RESET}")
                self.application.bot_data['last_error'] = str(e)

            self._prune_alert_cache()
            print(f"Global scan finished. Waiting {self.config.interval} seconds...")
            print("="*50)
            await asyncio.sleep(self.config.interval)

    async def _run_scan_cycle(self):
        """Runs a complete scan across all configured chains concurrently."""
        self._alerts_dispatched_in_cycle = 0
        self._current_scan_cycle_id = await self._record_scan_cycle_start()

        scan_tasks = [self._scan_chain(chain) for chain in self.config.chains]
        results = await asyncio.gather(*scan_tasks)
        
        all_simple_ops = [opp for res in results for opp in res[0]]
        all_multileg_ops = [opp for res in results for opp in res[1]]

        await self._process_opportunities(all_simple_ops, all_multileg_ops)
        
        self.application.bot_data['last_scan_time'] = time.strftime('%Y-%m-%d %H:%M:%S UTC')
        self.application.bot_data['found_last_scan'] = len(all_simple_ops) + len(all_multileg_ops)
        
        self.application.bot_data['last_scan_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
        self.application.bot_data['found_last_scan'] = len(all_simple_ops) + len(all_multileg_ops)

        await self._record_scan_cycle_finish(self._alerts_dispatched_in_cycle)
        self._current_scan_cycle_id = None

    async def _scan_chain(self, chain_name: str) -> Tuple[List[ArbitrageOpportunity], List[MultiLegArbitrageOpportunity]]:
        """Runs a single, complete scan for a given chain."""
        try:
            if self.config.multi_leg:
                return [], await self._scan_chain_multi_leg(chain_name)
            else:
                return await self._scan_chain_simple(chain_name), []
        except Exception as e:
            print(f"{C_RED}Error scanning chain {chain_name}: {e}{C_RESET}")
            return [], []

    async def _get_base_data_for_chain(self, chain_name: str) -> Tuple[Dict, float, float] | None:
        """Fetches native token price and gas price for a chain."""
        chain_info = CHAIN_CONFIG.get(chain_name)
        if not chain_info:
            print(f"{C_RED}Chain '{chain_name}' not found in CHAIN_CONFIG.{C_RESET}")
            return None

        print(f"Fetching required data for {C_BLUE}{chain_name.capitalize()}{C_RESET}...")
        try:
            price_task = self.dex_client.get_native_token_price_in_usd(chain_info)
            gas_task = self.etherscan_client.get_gas_price_in_gwei(chain_name, chain_info)
            native_price, gas_price = await asyncio.gather(price_task, gas_task)
        except Exception as e:
            print(f"{C_RED}Error fetching base data for {chain_name}: {e}{C_RESET}")
            return None

        if native_price is None or gas_price is None:
            print(f"{C_RED}Could not fetch required pricing data for {chain_name}. Skipping...{C_RESET}")
            return None
        
        native_symbol = chain_info['nativeSymbol']
        print(f"[{chain_name.capitalize()}] {native_symbol} Price: ${native_price:.2f}, Gas Price: {gas_price:.2f} Gwei")
        print("-" * 40)
        return chain_info, native_price, gas_price

    async def _scan_chain_simple(self, chain_name: str) -> List[ArbitrageOpportunity]:
        """Runs a simple 2-DEX arbitrage scan on a chain."""
        base_data = await self._get_base_data_for_chain(chain_name)
        if not base_data:
            return []
        _, native_price, gas_price = base_data

        token_tasks = [
            self._scan_token_on_chain(symbol, native_price, gas_price, chain_name)
            for symbol in self.config.tokens
        ]
        results = await asyncio.gather(*token_tasks)
        return [opp for sublist in results for opp in sublist]

    async def _scan_token_on_chain(
        self,
        token_symbol: str,
        native_price: float,
        gas_price: float,
        chain_name: str
    ) -> List[ArbitrageOpportunity]:
        """Scans a single token on a specific chain for opportunities."""
        print(f"Scanning token: {C_YELLOW}{token_symbol.upper()}{C_RESET} on {C_BLUE}{chain_name.capitalize()}{C_RESET}")
        try:
            api_data = await self.dex_client.search_dexscreener(token_symbol)
            if not api_data:
                print(f"No DexScreener data for {token_symbol.upper()} on {chain_name.capitalize()}")
                return []

            opportunities = self.analyzer.find_opportunities(
                api_data, token_symbol, native_price, gas_price, chain_name
            )
            if not opportunities:
                print(f"No profitable opportunities found for {token_symbol.upper()} on {chain_name.capitalize()}")
            return opportunities
        except Exception as e:
            print(f"{C_RED}Error scanning token {token_symbol.upper()} on {chain_name}: {e}{C_RESET}")
            return []

    async def _scan_chain_multi_leg(self, chain_name: str) -> List[MultiLegArbitrageOpportunity]:
        """Runs a multi-leg arbitrage scan on a chain."""
        base_data = await self._get_base_data_for_chain(chain_name)
        if not base_data:
            return []
        chain_info, native_price, gas_price = base_data
        gas_cost_usd = (gas_price * 1e-9) * 150000 * native_price # Estimate

        print(f"Starting multi-leg scan for {chain_name.capitalize()}. This may take a moment...")
        dexscreener_chain_name = chain_info['dexscreenerName']
        graph_data, token_map = await self._fetch_graph_data(chain_name, dexscreener_chain_name)
        self.token_map.update(token_map)

        if not graph_data:
            print(f"Could not fetch graph data for {chain_name.capitalize()}.")
            return []

        print(f"Building graph with {len(graph_data)} pairs...")
        graph = mla.build_graph_from_pairs(graph_data)

        print(f"Detecting cycles up to {self.config.max_cycle_length} legs...")
        opportunities = mla.find_multi_leg_opportunities(graph, self.config, gas_cost_usd, self.token_map, chain_name, graph_data)

        if not opportunities:
            print(f"No profitable multi-leg opportunities found on {chain_name.capitalize()}\n")

        return opportunities

    async def _fetch_graph_data(self, chain_name: str, dexscreener_chain_name: str) -> Tuple[List[Dict], Dict[str, str]]:
        """
        Builds the graph data using a more reliable, two-stage address-based search.
        """
        all_pairs = {}
        token_map = {}

        seed_addresses = await self._get_token_addresses(self.config.tokens, chain_name, dexscreener_chain_name)
        if not seed_addresses:
            print(f"{C_RED}Could not resolve addresses for any seed tokens on {chain_name}. Cannot build graph.{C_RESET}")
            return [], {}

        async def fetch_recursive(addresses_to_fetch: Set[str], current_depth: int):
            if not addresses_to_fetch or current_depth > self.config.max_depth:
                return

            print(f"Depth {current_depth}: Fetching pairs for {len(addresses_to_fetch)} addresses...")
            fetch_tasks = [self.dex_client.search_dexscreener(addr) for addr in addresses_to_fetch]
            results = await asyncio.gather(*fetch_tasks)

            next_level_addresses = set()

            for data in results:
                if not data or not data.get('pairs'):
                    continue

                for pair in data['pairs']:
                    try:
                        if pair['pairAddress'] in all_pairs:
                            continue

                        liq_usd = pair.get('liquidity', {}).get('usd', 0.0)
                        if liq_usd < self.config.min_liquidity:
                            continue

                        all_pairs[pair['pairAddress']] = pair

                        base_addr = pair['baseToken']['address']
                        quote_addr = pair['quoteToken']['address']

                        token_map[base_addr] = pair['baseToken']['symbol']
                        token_map[quote_addr] = pair['quoteToken']['symbol']

                        if current_depth < self.config.max_depth:
                            next_level_addresses.add(base_addr)
                            next_level_addresses.add(quote_addr)

                    except (KeyError, TypeError):
                        continue

            await fetch_recursive(next_level_addresses - addresses_to_fetch, current_depth + 1)

        await fetch_recursive(set(seed_addresses.values()), 1)

        if not all_pairs:
            print(f"{C_RED}Could not fetch any valid pairs for the seed tokens on {chain_name}.{C_RESET}")

        return list(all_pairs.values()), token_map

    async def _get_token_addresses(self, token_symbols: List[str], chain_name: str, dexscreener_chain_name: str) -> Dict[str, str]:
        """
        Gets the contract addresses for a list of token symbols using a cache-first approach.
        """
        from constants import COMMON_TOKEN_ADDRESSES
        addresses = {}
        chain_addresses = COMMON_TOKEN_ADDRESSES.get(chain_name, {})
        
        robust_quote_symbols = {
            "USDC", "USDT", "DAI", "WETH", "WBTC", "WMATIC", "WBNB", "ETH", "BNB", "MATIC",
            "BUSD", "FRAX", "LINK", "UNI", "AAVE", "CRV", "BAL", "SUSHI", "1INCH", "CAKE",
            "DOGE", "SHIB", "PEPE", "FLOKI", "YFI"
        }

        for symbol in token_symbols:
            symbol_lower = symbol.lower()
            found_address = None

            if symbol_lower in chain_addresses:
                found_address = chain_addresses[symbol_lower]
                print(f"Found cached address for {C_YELLOW}{symbol.upper()}{C_RESET} on {chain_name}: {found_address}")
                addresses[symbol] = found_address
                continue

            print(f"No cached address for {C_YELLOW}{symbol.upper()}{C_RESET} on {chain_name}, searching via API...")
            
            pair_search_queries = [f"{symbol.upper()}/{qs}" for qs in robust_quote_symbols if symbol.upper() != qs]
            pair_search_queries += [f"{qs}/{symbol.upper()}" for qs in robust_quote_symbols if symbol.upper() != qs]

            if not pair_search_queries:
                print(f"{C_RED}No suitable pair queries for {symbol.upper()} on {chain_name}.{C_RESET}")
                continue

            BATCH_SIZE = 5
            for i in range(0, len(pair_search_queries), BATCH_SIZE):
                batch_queries = pair_search_queries[i:i + BATCH_SIZE]
                search_tasks = [self.dex_client.search_dexscreener(query) for query in batch_queries]
                results = await asyncio.gather(*search_tasks)

                for data in results:
                    if not data or not data.get('pairs'):
                        continue
                    for pair in data['pairs']:
                        if pair.get('chainId') == dexscreener_chain_name:
                            if pair['baseToken']['symbol'].lower() == symbol_lower:
                                found_address = pair['baseToken']['address']
                                break
                            elif pair['quoteToken']['symbol'].lower() == symbol_lower:
                                found_address = pair['quoteToken']['address']
                                break
                    if found_address: break
                if found_address: break
                if i + BATCH_SIZE < len(pair_search_queries): await asyncio.sleep(1)

            if found_address:
                addresses[symbol] = found_address
                print(f"Found address for {C_YELLOW}{symbol.upper()}{C_RESET} on {chain_name} via API: {found_address}")
            else:
                print(f"{C_RED}Could not find an address for {symbol.upper()} on {chain_name} via API.{C_RESET}")

        return addresses

    async def _process_opportunities(self, simple_ops: List[ArbitrageOpportunity], multileg_ops: List[MultiLegArbitrageOpportunity]):
        """Prints and sends alerts for all found opportunities."""
        total_found = len(simple_ops) + len(multileg_ops)
        if total_found > 0:
            simple_ops.sort(key=lambda x: x.net_profit_usd, reverse=True)
            for opp in simple_ops:
                self._print_opportunity(opp)
                if self.config.telegram_enabled:
                    await self._send_telegram_notification(opp)
            
            multileg_ops.sort(key=lambda x: x.net_profit_usd, reverse=True)
            for opp in multileg_ops:
                self._print_multi_leg_opportunity(opp)
                if self.config.telegram_enabled:
                    await self._send_multi_leg_telegram_notification(opp)
        
        print("-" * 40)
        print(f"Scan complete. Found {total_found} total profitable opportunities.")

    def _print_opportunity(self, opp: ArbitrageOpportunity):
        """Formats and prints a single opportunity to the console."""
        display_gas_cost = 0.01 if opp.gas_cost_usd < 0.01 else opp.gas_cost_usd
        print(f"OPPORTUNITY: {opp.pair_name} on {opp.chain_name.capitalize()}"
              f" | Profit: ${opp.net_profit_usd:.2f}")

    async def _send_telegram_notification(self, opp: ArbitrageOpportunity):
        """Checks cooldown, calculates momentum, and sends a Telegram alert."""
        now = time.time()
        opp_key = f"{opp.chain_name}-{opp.pair_name}-{opp.buy_dex}-{opp.sell_dex}"

        if opp_key not in self.alert_cache or (now - self.alert_cache[opp_key]) > self.config.alert_cooldown:
            print(f"{C_BLUE}Processing momentum candidate for {opp.pair_name}...{C_RESET}")
            
            high_price_dex_name = await self._resolve_dex_name(opp.sell_dex, opp.chain_name)
            low_price_dex_name = await self._resolve_dex_name(opp.buy_dex, opp.chain_name)

            if 'vault' in high_price_dex_name.lower() or 'vault' in low_price_dex_name.lower():
                return

            token_symbol = opp.pair_name.split('/')[0]
            self.opportunity_persistence.setdefault(opp_key, []).append(now)
            self.opportunity_persistence[opp_key] = [t for t in self.opportunity_persistence[opp_key] if now - t < 600]
            persistence_count = len(self.opportunity_persistence[opp_key])

            dominant_volume = opp.buy_dex_volume_usd if opp.dominant_is_buy_side else opp.sell_dex_volume_usd
            other_volume = opp.sell_dex_volume_usd if opp.dominant_is_buy_side else opp.buy_dex_volume_usd
            volume_divergence = dominant_volume / other_volume if other_volume > 0 else float('inf')
            dominant_dex_has_lower_price = opp.dominant_is_buy_side

            momentum_history = await self._load_recent_momentum_history(token_symbol, opp.direction)
            last_known_rsi = next(
                (entry.get("rsi_value") for entry in momentum_history if entry.get("rsi_value") is not None),
                None,
            )

            rsi_value = 50
            base_rsi = rsi_value
            ema_rsi = None
            ema_alpha = 2 / (min(len(momentum_history), 5) + 1) if momentum_history else None
            if last_known_rsi is not None:
                ema_rsi = last_known_rsi

            if momentum_history and last_known_rsi is not None and ema_alpha is not None:
                for record in momentum_history[1:]:
                    value = record.get("rsi_value")
                    if value is not None:
                        ema_rsi = (value * ema_alpha) + (ema_rsi * (1 - ema_alpha)) if ema_rsi is not None else value

            if ema_rsi is None and last_known_rsi is not None:
                ema_rsi = last_known_rsi

            try:
                coin_id = self._coin_id_cache.get(token_symbol)
                if not coin_id:
                    search_result = await self.coingecko_client.search_coin(token_symbol)
                    if search_result and search_result.get('id'):
                        coin_id = search_result['id']
                        self._coin_id_cache[token_symbol] = coin_id
                
                if coin_id:
                    fetched_rsi = await self.coingecko_client.get_rsi(coin_id)
                    if fetched_rsi is not None:
                        rsi_value = fetched_rsi
                        base_rsi = rsi_value
                        print(f"Successfully fetched RSI for {token_symbol}: {rsi_value:.2f}")
                    elif last_known_rsi is not None:
                        rsi_value = last_known_rsi
                        base_rsi = rsi_value
                        print(f"Using cached RSI for {token_symbol}: {rsi_value:.2f}")
                    else:
                        print(f"{C_YELLOW}Falling back to neutral RSI for {token_symbol}.{C_RESET}")
                elif last_known_rsi is not None:
                    rsi_value = last_known_rsi
                    base_rsi = rsi_value
                    print(f"Using cached RSI (no CoinGecko id) for {token_symbol}: {rsi_value:.2f}")
            except Exception as e:
                print(f"{C_RED}Error fetching RSI for {token_symbol}: {e}{C_RESET}")
                if last_known_rsi is not None:
                    rsi_value = last_known_rsi
                    base_rsi = rsi_value
                    print(f"Using cached RSI after error for {token_symbol}: {rsi_value:.2f}")

            volume_norm = min(volume_divergence if math.isfinite(volume_divergence) else 5.0, 5.0) / 5.0
            persistence_norm = min(persistence_count, 5) / 5
            flow_bias = (volume_norm + persistence_norm) / 2

            base_rsi = ema_rsi if ema_rsi is not None else base_rsi
            blended_rsi = base_rsi + (flow_bias - 0.5) * 10
            blended_rsi = max(0.0, min(blended_rsi, 100.0))

            momentum_score, momentum_explanation = calculate_momentum_score(
                volume_divergence=volume_divergence,
                persistence_count=persistence_count,
                rsi_value=blended_rsi,
                dominant_dex_has_lower_price=dominant_dex_has_lower_price
            )

            if opp.direction == 'BULLISH' and momentum_score < self.config.min_momentum_score_bullish:
                print(f"{C_YELLOW}Skipping signal for {opp.pair_name} due to low momentum score ({momentum_score:.1f} < {self.config.min_momentum_score_bullish:.1f}).{C_RESET}")
                return
            if opp.direction == 'BEARISH' and momentum_score < self.config.min_momentum_score_bearish:
                print(f"{C_YELLOW}Skipping signal for {opp.pair_name} due to low momentum score ({momentum_score:.1f} < {self.config.min_momentum_score_bearish:.1f}).{C_RESET}")
                return

            if not self.config.ai_analysis_enabled:
                ai_analysis = "AI analysis disabled by configuration."
                twitter_summary = "AI analysis disabled."
            else:
                ai_analysis = "AI analysis unavailable."
                twitter_summary = ""
                if self.gemini_client and self.config.gemini_api_key:
                    opportunity_data = {
                        "direction": opp.direction,
                        "symbol": token_symbol,
                        "chain": opp.chain_name.capitalize(),
                        "profit_percentage": opp.gross_diff_pct,
                        "momentum_score": momentum_score,
                        "current_price": opp.sell_price if opp.direction == 'BULLISH' else opp.buy_price,
                        "buy_dex": opp.buy_dex,
                        "sell_dex": opp.sell_dex,
                        "buy_price": opp.buy_price,
                        "sell_price": opp.sell_price,
                        "net_profit_usd": opp.net_profit_usd,
                        "effective_volume": opp.effective_volume,
                        "momentum_explanation": momentum_explanation,
                        "momentum_breakdown": {
                            "volume_divergence": volume_divergence,
                            "persistence_count": persistence_count,
                            "rsi_value": rsi_value,
                            "dominant_flow_side": "buy" if dominant_dex_has_lower_price else "sell",
                            "dominant_volume_ratio": opp.dominant_volume_ratio,
                            "short_term_volume_ratio": opp.short_term_volume_ratio,
                            "short_term_txns_total": opp.short_term_txns_total,
                            "is_early_momentum": opp.is_early_momentum,
                        },
                        "momentum_history": momentum_history,
                    }
                    try:
                        analysis_result = await self.gemini_client.generate_token_analysis(opportunity_data)
                        ai_analysis = analysis_result.telegram_detail
                        twitter_summary = analysis_result.twitter_summary
                    except Exception as e:
                        print(f"{C_RED}Error generating Gemini analysis: {e}{C_RESET}")
                        ai_analysis = "AI analysis failed to generate."
                        twitter_summary = "AI analysis unavailable."

            message = self.format_signal_message(opp, ai_analysis, momentum_score, low_price_dex_name, high_price_dex_name, self.config.ai_analysis_enabled)
            
            await self.bot.send_message(
                chat_id=self.config.telegram_chat_id,
                text=message,
                parse_mode='HTML'
            )

            await self._persist_momentum_snapshot(
                opp=opp,
                momentum_score=momentum_score,
                volume_divergence=volume_divergence,
                persistence_count=persistence_count,
                rsi_value=rsi_value,
                base_rsi=base_rsi,
                dominant_dex_has_lower_price=dominant_dex_has_lower_price,
                opportunity_key=opp_key,
                dispatched_at=now,
                momentum_explanation=momentum_explanation,
                momentum_history=momentum_history,
            )
            self._alerts_dispatched_in_cycle += 1
            self.alert_cache[opp_key] = now

            # --- Twitter Integration ---
            if self.config.twitter_enabled and self.twitter_client:
                if not self.config.ai_analysis_enabled:
                    print(f"{C_YELLOW}AI analysis disabled; skipping tweet generation.{C_RESET}")
                elif not self.gemini_client or not self.config.gemini_api_key:
                    print(f"{C_YELLOW}Gemini client unavailable; skipping tweet generation.{C_RESET}")
                else:
                    try:
                        tweet_payload = twitter_summary or ai_analysis
                        print(f"{C_GREEN}Posting tweet: {tweet_payload}{C_RESET}")
                        self.twitter_client.post_tweet(tweet_payload)
                    except Exception as e:
                        print(f"{C_RED}Error during Twitter processing: {e}{C_RESET}")

        else:
            print(f"{C_YELLOW}Skipping notification for {opp.pair_name} (cooldown).{C_RESET}")

    async def _load_recent_momentum_history(self, token_symbol: str, direction: str, limit: int = 3) -> list[dict]:
        if not self.repository:
            return []
        try:
            records = await self.repository.fetch_momentum_records(
                limit=limit,
                token=token_symbol.upper(),
                direction=direction,
            )
        except Exception as exc:
            print(f"{C_RED}Failed to load momentum history for {token_symbol}: {exc}{C_RESET}")
            return []

        history: list[dict] = []
        for record in records:
            alert_time = record.get("alert_time")
            history.append({
                "timestamp_utc": alert_time.strftime("%Y-%m-%d %H:%M:%S") if alert_time else None,
                "momentum_score": record.get("momentum_score"),
                "spread_pct": record.get("spread_pct"),
                "net_profit_usd": record.get("net_profit_usd"),
                "clip_usd": record.get("effective_volume_usd"),
                "rsi_value": record.get("rsi_value"),
            })
        return history

    async def _record_scan_cycle_start(self) -> Optional[int]:
        if not self.repository:
            return None
        try:
            return await self.repository.record_scan_cycle_start(self.config.chains, self.config.tokens)
        except Exception as exc:
            print(f"{C_RED}Failed to persist scan cycle start: {exc}{C_RESET}")
            return None

    async def _record_scan_cycle_finish(self, opportunities_found: int) -> None:
        if not self.repository or self._current_scan_cycle_id is None:
            return
        try:
            await self.repository.record_scan_cycle_finish(self._current_scan_cycle_id, opportunities_found)
        except Exception as exc:
            print(f"{C_RED}Failed to persist scan cycle finish: {exc}{C_RESET}")

    async def _persist_momentum_snapshot(
        self,
        *,
        opp: ArbitrageOpportunity,
        momentum_score: float,
        volume_divergence: float,
        persistence_count: int,
        rsi_value: float,
        base_rsi: float,
        dominant_dex_has_lower_price: bool,
        opportunity_key: str,
        dispatched_at: float,
        momentum_explanation: str | None,
        momentum_history: list[dict],
    ) -> None:
        if not self.repository:
            return

        try:
            token_symbol = opp.pair_name.split('/')[0]
            volume_divergence_value = None if math.isinf(volume_divergence) else volume_divergence
            dispatched_dt = datetime.fromtimestamp(dispatched_at, timezone.utc)
            raw_payload = {
                "pair_name": opp.pair_name,
                "chain": opp.chain_name,
                "direction": opp.direction,
                "buy_dex": opp.buy_dex,
                "sell_dex": opp.sell_dex,
                "effective_volume_usd": opp.effective_volume,
                "gas_cost_usd": opp.gas_cost_usd,
                "dex_fee_cost_usd": opp.dex_fee_cost,
                "slippage_cost_usd": opp.slippage_cost,
                "price_impact_pct": opp.price_impact_pct,
                "spread_pct": opp.gross_diff_pct,
                "net_profit_usd": opp.net_profit_usd,
                "momentum_explanation": momentum_explanation,
                "base_rsi": base_rsi,
                "blended_rsi": blended_rsi,
                "dominant_volume_ratio": opp.dominant_volume_ratio,
                "dominant_flow_side": "buy" if opp.dominant_is_buy_side else "sell",
                "momentum": {
                    "score": momentum_score,
                    "volume_divergence": volume_divergence_value,
                    "persistence_count": persistence_count,
                    "rsi_value": rsi_value,
                    "dominant_dex_has_lower_price": dominant_dex_has_lower_price,
                    "dominant_volume_ratio": opp.dominant_volume_ratio,
                    "short_term_volume_ratio": opp.short_term_volume_ratio,
                    "short_term_txns_total": opp.short_term_txns_total,
                },
                "trend": {
                    "buy_price_change_h1": opp.buy_price_change_h1,
                    "sell_price_change_h1": opp.sell_price_change_h1,
                },
                "is_early_momentum": opp.is_early_momentum,
                "recent_momentum_history": momentum_history,
            }

            await self.repository.record_opportunity_alert(
                scan_cycle_id=self._current_scan_cycle_id,
                chain=opp.chain_name,
                token=token_symbol.upper(),
                direction=opp.direction,
                net_profit_usd=opp.net_profit_usd,
                gross_profit_usd=opp.gross_profit_usd,
                momentum_score=momentum_score,
                opportunity_key=opportunity_key,
                alert_sent_at=dispatched_dt,
                volume_divergence=volume_divergence_value,
                persistence_count=persistence_count,
                rsi_value=rsi_value,
                dominant_dex_has_lower_price=dominant_dex_has_lower_price,
                raw_payload=raw_payload,
            )
        except Exception as exc:
            print(f"{C_RED}Failed to persist momentum snapshot: {exc}{C_RESET}")

    def _prune_alert_cache(self):
        """Removes expired entries from the alert cache."""
        now = time.time()
        self.alert_cache = {k: v for k, v in self.alert_cache.items() if (now - v) < self.config.alert_cooldown}

    async def _resolve_dex_name(self, dex_identifier: str, chain_name: str) -> str:
        """Resolves a DEX identifier to a name."""
        if not dex_identifier.startswith("0x"):
            return dex_identifier

        if chain_name == 'base':
            name = await self.blockscout_client.get_contract_name(dex_identifier)
            if name: return name
        
        short_address = f"{dex_identifier[:6]}...{dex_identifier[-4:]}"
        return f"<a href='https://base.blockscout.com/address/{dex_identifier}'>{short_address}</a>"

    def format_signal_message(
        self, opp: ArbitrageOpportunity, ai_analysis: str, momentum_score: float,
        buy_dex_name: str, sell_dex_name: str, analysis_enabled: bool
    ) -> str:
        """Formats a direction-neutral momentum alert for Telegram."""

        token_symbol = opp.pair_name.split('/')[0]
        header_emoji = "⚡"
        disclaimer = "<i>Disclaimer: This is not financial advice.</i>"

        analysis_content = (
            f"<pre>{ai_analysis}</pre>"
            if analysis_enabled else "AI analysis disabled."
        )

        def _format_percent(value: float) -> str:
            return f"{value:+.2f}%"

        trend_bits: list[str] = []
        if opp.buy_price_change_h1 is not None:
            trend_bits.append(f"Buy 1h change {_format_percent(opp.buy_price_change_h1)}")
        if opp.sell_price_change_h1 is not None:
            trend_bits.append(f"Sell 1h change {_format_percent(opp.sell_price_change_h1)}")
        trend_line = f"<b>Trend:</b> {' | '.join(trend_bits)}" if trend_bits else ""

        flow_details = ""
        if opp.dominant_volume_ratio and math.isfinite(opp.dominant_volume_ratio):
            flow_side = "buy" if opp.dominant_is_buy_side else "sell"
            flow_details = f"<b>Flow:</b> {opp.dominant_volume_ratio:.2f}x {flow_side}-side volume vs other venue"

        notes_bits: list[str] = []
        if opp.is_early_momentum:
            notes_bits.append("Early momentum pattern")
        notes_line = f"<b>Notes:</b> {' | '.join(notes_bits)}" if notes_bits else ""

        message_lines: list[str] = [
            f"{header_emoji} <b>Momentum Spike: {token_symbol.upper()} on {opp.chain_name.capitalize()}</b>",
            "",
            f"<b>Spread:</b> {opp.gross_diff_pct:.2f}% | <b>Momentum Score:</b> {momentum_score:.1f}/10",
            f"<b>Route:</b> Buy {buy_dex_name} @ ${opp.buy_price:.6f} -> Sell {sell_dex_name} @ ${opp.sell_price:.6f}",
            f"<b>Est. Net:</b> ${opp.net_profit_usd:.2f} on ${opp.effective_volume:,.0f}",
        ]

        for optional_line in (trend_line, flow_details, notes_line):
            if optional_line:
                message_lines.append(optional_line)

        message_lines.extend([
            "",
            analysis_content,
            "",
            disclaimer,
        ])

        return "\n".join(message_lines)
