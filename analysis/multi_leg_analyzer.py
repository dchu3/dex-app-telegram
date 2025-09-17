#!/usr/bin/env python3
import math
from typing import List, Dict, Any, Tuple

import networkx as nx

from analysis.models import MultiLegArbitrageOpportunity
from config import AppConfig

def build_graph_from_pairs(pairs_data: List[Dict[str, Any]]) -> nx.DiGraph:
    """
    Builds a directed graph from a list of trading pairs.
    Nodes are token addresses, edges are weighted with the negative log of the exchange rate.
    """
    graph = nx.DiGraph()
    for pair in pairs_data:
        try:
            base_token_addr = pair['baseToken']['address']
            quote_token_addr = pair['quoteToken']['address']
            
            # Use priceNative for direct exchange rate, otherwise calculate from USD prices
            if pair.get('priceNative'):
                rate_base_to_quote = float(pair['priceNative'])
            elif pair.get('baseToken', {}).get('priceUsd') and pair.get('quoteToken', {}).get('priceUsd'):
                base_price_usd = float(pair['baseToken']['priceUsd'])
                quote_price_usd = float(pair['quoteToken']['priceUsd'])
                if base_price_usd > 0 and quote_price_usd > 0:
                    rate_base_to_quote = base_price_usd / quote_price_usd
                else:
                    continue
            else:
                continue

            if rate_base_to_quote > 0:
                # Add edges for both trading directions
                # Store extra info on the edge for later calculations
                graph.add_edge(
                    base_token_addr,
                    quote_token_addr,
                    weight=-math.log(rate_base_to_quote),
                    rate=rate_base_to_quote,
                    pair_info=pair
                )
                graph.add_edge(
                    quote_token_addr,
                    base_token_addr,
                    weight=-math.log(1 / rate_base_to_quote),
                    rate=(1 / rate_base_to_quote),
                    pair_info=pair
                )
        except (ValueError, TypeError, KeyError):
            continue # Skip pairs with malformed data
    return graph

def calculate_cycle_profitability(
    cycle: List[str],
    graph: nx.DiGraph,
    config: AppConfig,
    gas_cost_usd: float,
    token_map: Dict[str, str],
    chain_name: str,
    token_prices_usd: Dict[str, float]
) -> MultiLegArbitrageOpportunity | None:
    """
    Calculates the net profit of an arbitrage cycle after all fees and costs.
    """
    num_swaps = len(cycle)
    
    start_token_address = cycle[0]
    start_token_price_usd = token_prices_usd.get(start_token_address)

    if not start_token_price_usd or start_token_price_usd <= 0:
        return None # Cannot calculate profit without a valid starting price

    initial_token_quantity = config.trade_volume / start_token_price_usd
    current_token_quantity = initial_token_quantity

    # Apply fees for each swap in the cycle
    for i in range(num_swaps):
        u = cycle[i]
        v = cycle[(i + 1) % num_swaps]
        
        edge_data = graph.get_edge_data(u, v)
        rate = edge_data['rate']
        
        current_token_quantity *= rate
        # Deduct DEX fee and slippage for each leg of the trade
        current_token_quantity *= (1 - config.dex_fee / 100.0)
        current_token_quantity *= (1 - config.slippage / 100.0)

    final_amount_usd = current_token_quantity * start_token_price_usd
    gross_profit_usd = final_amount_usd - config.trade_volume
    total_gas_cost = gas_cost_usd * num_swaps
    net_profit_usd = gross_profit_usd - total_gas_cost

    cycle_path_symbols = [token_map.get(addr, addr[:6]) for addr in cycle] + [token_map.get(cycle[0], cycle[0][:6])]

    if net_profit_usd > config.min_profit:
        return MultiLegArbitrageOpportunity(
            chain_name=chain_name,
            cycle_path=cycle_path_symbols,
            gross_profit_usd=gross_profit_usd,
            net_profit_usd=net_profit_usd,
            trade_volume_usd=config.trade_volume,
            gas_cost_usd=total_gas_cost,
            num_swaps=num_swaps
        )
    return None

def find_multi_leg_opportunities(
    graph: nx.DiGraph,
    config: AppConfig,
    gas_cost_usd: float,
    token_map: Dict[str, str],
    chain_name: str,
    all_raw_pairs_data: List[Dict[str, Any]]
) -> List[MultiLegArbitrageOpportunity]:
    """
    Finds all profitable arbitrage cycles in the graph up to a max length.
    """
    opportunities = []
    token_prices_usd: Dict[str, float] = {}

    # Build a map of token address to its USD price from all available pairs
    for pair in all_raw_pairs_data:
        try:
            base_addr = pair['baseToken']['address']
            quote_addr = pair['quoteToken']['address']
            
            if pair['baseToken'].get('priceUsd'):
                token_prices_usd[base_addr] = float(pair['baseToken']['priceUsd'])
            if pair['quoteToken'].get('priceUsd'):
                token_prices_usd[quote_addr] = float(pair['quoteToken']['priceUsd'])
        except (KeyError, TypeError, ValueError):
            continue

    # Use simple_cycles to find all paths that start and end at the same node
    cycles = list(nx.simple_cycles(graph, length_bound=config.max_cycle_length))
    
    for cycle in cycles:
        if len(cycle) < 3: # Triangular is the minimum
            continue

        # Check for negative cycle (product of rates > 1)
        edges_in_cycle = [(cycle[i], cycle[(i + 1) % len(cycle)]) for i in range(len(cycle))]
        path_weight = sum(graph[u][v]['weight'] for u, v in edges_in_cycle)
        
        if path_weight < 0:
            opportunity = calculate_cycle_profitability(cycle, graph, config, gas_cost_usd, token_map, chain_name, token_prices_usd)
            if opportunity:
                opportunities.append(opportunity)
                
    return opportunities
