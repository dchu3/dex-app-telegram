
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pytest
from config import AppConfig
from analysis.analyzer import OpportunityAnalyzer

@pytest.fixture
def config():
    return AppConfig(
        chains=['ethereum'],
        tokens=['WETH'],
        dex_fee=0.3,
        slippage=0.5,
        min_bullish_profit=0.0,
        min_bearish_discrepancy=1.0,
        min_momentum_score_bullish=0.0,
        min_momentum_score_bearish=0.0,
        trade_volume=100.0,
        min_liquidity=1000.0,
        min_volume=0.0,
        min_txns_h1=1,
        interval=60,
        min_profit=0.0,
        telegram_enabled=False,
        alert_cooldown=3600,
        etherscan_api_key='dummy',
        telegram_bot_token=None,
        telegram_chat_id=None,
        coingecko_api_key=None,
        gemini_api_key=None,
        ai_analysis_enabled=True,
        twitter_enabled=False,
        min_tweet_momentum_score=7.0,
        twitter_api_key=None,
        twitter_api_secret=None,
        twitter_access_token=None,
        twitter_access_token_secret=None,
        multi_leg=False,
        max_cycle_length=3,
        max_depth=2,
        scanner_enabled=False,
        show_momentum=False,
        momentum_limit=10,
        momentum_token=None,
        momentum_direction=None,
        limit_base_dexes=False,
        integration_test=False,
        auto_trade=False,
        trade_rpc_url=None,
        trade_wallet_address=None,
        trade_max_slippage=1.0,
        trading_private_key=None,
    )

# def test_profitable_opportunity(config):
#     analyzer = OpportunityAnalyzer(config)
#     pairs_data = {
#         'pairs': [
#             {
#                 'chainId': 'ethereum', 'dexId': 'uniswap', 'priceUsd': '2000',
#                 'baseToken': {'symbol': 'WETH', 'address': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'}, 'quoteToken': {'symbol': 'USDC'},
#                 'liquidity': {'usd': 50000}, 'volume': {'h24': 10000}, 'priceNative': '1',
#                 'txns': {'h1': {'buys': 10, 'sells': 10}}
#             },
#             {
#                 'chainId': 'ethereum', 'dexId': 'sushiswap', 'priceUsd': '2050',
#                 'baseToken': {'symbol': 'WETH', 'address': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'}, 'quoteToken': {'symbol': 'USDC'},
#                 'liquidity': {'usd': 50000}, 'volume': {'h24': 10000}, 'priceNative': '1.025',
#                 'txns': {'h1': {'buys': 10, 'sells': 10}}
#             }
#         ]
#     }
#     opportunities = analyzer.find_opportunities(pairs_data, 'WETH', 2000.0, 20.0, 'ethereum')
#     assert len(opportunities) == 1
#     opp = opportunities[0]
#     assert opp.buy_dex == 'uniswap'
#     assert opp.sell_dex == 'sushiswap'
#     assert opp.net_profit_usd > 0.0


def test_direction_bullish_uses_dominant_volume(config):
    analyzer = OpportunityAnalyzer(config)
    pairs_data = {
        'pairs': [
            {
                'chainId': 'ethereum',
                'dexId': 'dominantdex',
                'priceUsd': '100',
                'priceNative': '1',
                'baseToken': {'symbol': 'WETH', 'address': '0xbase'},
                'quoteToken': {'symbol': 'USDC', 'address': '0xquote'},
                'liquidity': {'usd': 50000},
                'volume': {'h24': 80000},
                'txns': {'h1': {'buys': 5, 'sells': 5}},
            },
            {
                'chainId': 'ethereum',
                'dexId': 'otherdex',
                'priceUsd': '105',
                'priceNative': '1.05',
                'baseToken': {'symbol': 'WETH', 'address': '0xbase'},
                'quoteToken': {'symbol': 'USDC', 'address': '0xquote'},
                'liquidity': {'usd': 50000},
                'volume': {'h24': 20000},
                'txns': {'h1': {'buys': 5, 'sells': 5}},
            },
        ]
    }

    opportunities = analyzer.find_opportunities(pairs_data, 'WETH', 2000.0, 0.0, 'ethereum')

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.direction == 'BULLISH'
    assert opp.buy_dex == 'dominantdex'
    assert opp.sell_dex == 'otherdex'
    assert opp.dominant_is_buy_side is True
    assert opp.net_profit_usd > 0



def test_direction_bearish_uses_dominant_volume(config):
    analyzer = OpportunityAnalyzer(config)
    pairs_data = {
        'pairs': [
            {
                'chainId': 'ethereum',
                'dexId': 'dominantdex',
                'priceUsd': '105',
                'priceNative': '1.05',
                'baseToken': {'symbol': 'WETH', 'address': '0xbase'},
                'quoteToken': {'symbol': 'USDC', 'address': '0xquote'},
                'liquidity': {'usd': 50000},
                'volume': {'h24': 80000},
                'txns': {'h1': {'buys': 5, 'sells': 5}},
            },
            {
                'chainId': 'ethereum',
                'dexId': 'otherdex',
                'priceUsd': '100',
                'priceNative': '1',
                'baseToken': {'symbol': 'WETH', 'address': '0xbase'},
                'quoteToken': {'symbol': 'USDC', 'address': '0xquote'},
                'liquidity': {'usd': 50000},
                'volume': {'h24': 20000},
                'txns': {'h1': {'buys': 5, 'sells': 5}},
            },
        ]
    }

    opportunities = analyzer.find_opportunities(pairs_data, 'WETH', 2000.0, 0.0, 'ethereum')

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.direction == 'BEARISH'
    assert opp.buy_dex == 'otherdex'
    assert opp.sell_dex == 'dominantdex'
    assert opp.dominant_is_buy_side is False
    assert opp.net_profit_usd > 0


def test_base_chain_filters_disallowed_dex(config):
    config = config._replace(chains=['base'], limit_base_dexes=True)
    analyzer = OpportunityAnalyzer(config)
    pairs_data = {
        'pairs': [
            {
                'chainId': 'base',
                'dexId': 'aerodrome',
                'priceUsd': '1.00',
                'priceNative': '1.00',
                'baseToken': {'symbol': 'BRETT', 'address': '0xbase'},
                'quoteToken': {'symbol': 'USDC', 'address': '0xquote'},
                'liquidity': {'usd': 1000000},
                'volume': {'h24': 500000, 'm5': 30000},
                'txns': {'h1': {'buys': 10, 'sells': 10}, 'm5': {'buys': 3, 'sells': 3}},
            },
            {
                'chainId': 'base',
                'dexId': 'randomdex',
                'priceUsd': '1.05',
                'priceNative': '1.05',
                'baseToken': {'symbol': 'BRETT', 'address': '0xbase'},
                'quoteToken': {'symbol': 'USDC', 'address': '0xquote'},
                'liquidity': {'usd': 1000000},
                'volume': {'h24': 500000, 'm5': 30000},
                'txns': {'h1': {'buys': 10, 'sells': 10}, 'm5': {'buys': 3, 'sells': 3}},
            },
        ]
    }

    opportunities = analyzer.find_opportunities(pairs_data, 'BRETT', 1.0, 0.0, 'base')
    assert opportunities == []


def test_base_chain_allows_uniswap_and_aerodrome(config):
    config = config._replace(chains=['base'], limit_base_dexes=True)
    analyzer = OpportunityAnalyzer(config)
    pairs_data = {
        'pairs': [
            {
                'chainId': 'base',
                'dexId': 'aerodrome',
                'priceUsd': '1.00',
                'priceNative': '1.00',
                'baseToken': {'symbol': 'BRETT', 'address': '0xbase'},
                'quoteToken': {'symbol': 'USDC', 'address': '0xquote'},
                'liquidity': {'usd': 1000000},
                'volume': {'h24': 500000, 'm5': 30000},
                'txns': {'h1': {'buys': 10, 'sells': 10}, 'm5': {'buys': 3, 'sells': 3}},
            },
            {
                'chainId': 'base',
                'dexId': 'uniswap',
                'priceUsd': '1.05',
                'priceNative': '1.05',
                'baseToken': {'symbol': 'BRETT', 'address': '0xbase'},
                'quoteToken': {'symbol': 'USDC', 'address': '0xquote'},
                'liquidity': {'usd': 1000000},
                'volume': {'h24': 500000, 'm5': 30000},
                'txns': {'h1': {'buys': 10, 'sells': 10}, 'm5': {'buys': 3, 'sells': 3}},
            },
        ]
    }

    opportunities = analyzer.find_opportunities(pairs_data, 'BRETT', 1.0, 0.0, 'base')
    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.buy_dex == 'aerodrome'
    assert opp.sell_dex == 'uniswap'
