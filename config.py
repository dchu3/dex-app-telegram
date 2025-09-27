#!/usr/bin/env python3
import os
import argparse
from typing import NamedTuple
import constants

class AppConfig(NamedTuple):
    """Typed configuration object."""
    chains: list[str]
    tokens: list[str]
    dex_fee: float
    slippage: float
    min_bullish_profit: float
    min_bearish_discrepancy: float
    min_momentum_score_bullish: float
    min_momentum_score_bearish: float
    trade_volume: float
    min_liquidity: float
    min_volume: float
    min_txns_h1: int
    interval: int
    min_profit: float
    telegram_enabled: bool
    alert_cooldown: int
    etherscan_api_key: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    coingecko_api_key: str | None
    gemini_api_key: str | None
    ai_analysis_enabled: bool
    twitter_enabled: bool
    min_tweet_momentum_score: float
    twitter_api_key: str | None
    twitter_api_secret: str | None
    twitter_access_token: str | None
    twitter_access_token_secret: str | None
    multi_leg: bool
    max_cycle_length: int
    max_depth: int
    scanner_enabled: bool
    show_momentum: bool
    momentum_limit: int
    momentum_token: str | None
    momentum_direction: str | None
    limit_base_dexes: bool
    integration_test: bool
    auto_trade: bool
    trade_rpc_url: str | None
    trade_wallet_address: str | None
    trade_max_slippage: float
    trading_private_key: str | None


def load_config() -> AppConfig:
    """
    Parses command-line arguments and loads environment variables to create a configuration object.
    """
    parser = argparse.ArgumentParser(
        description="Find potential arbitrage opportunities for multiple tokens on multiple DEXs and chains.",
        epilog="Example: ./main.py --chain polygon ethereum --token WMATIC --min-profit 1.00"
    )
    # --- Existing Arguments ---
    parser.add_argument('--chain', nargs='+', choices=constants.CHAIN_CONFIG.keys(), help='One or more blockchains to scan.')
    parser.add_argument('--token', nargs='+', help='One or more token symbols to search for.')
    parser.add_argument('--dex-fee', type=float, default=0.3, help='DEX fee percentage (default: 0.3).')
    parser.add_argument('--slippage', type=float, default=0.5, help='Slippage tolerance percentage (default: 0.5).')
    parser.add_argument('--min-bullish-profit', type=float, default=0.0, help='Minimum net profit in USD for a bullish signal (default: 0.0).')
    parser.add_argument('--min-bearish-discrepancy', type=float, default=1.0, help='Minimum price discrepancy percentage for a bearish signal (default: 1.0).')
    parser.add_argument('--min-momentum-score-bullish', type=float, default=0.0, help='Minimum momentum score (0-10) required to trigger a bullish alert (default: 0.0).')
    parser.add_argument('--min-momentum-score-bearish', type=float, default=0.0, help='Minimum momentum score (0-10) required to trigger a bearish alert (default: 0.0).')
    parser.add_argument('--trade-volume', type=float, default=500.0, help='Trade volume in USD for estimates (default: 500).')
    parser.add_argument('--min-liquidity', type=float, default=1000.0, help='Min USD liquidity per pair (default: 1000).')
    parser.add_argument('--min-volume', type=float, default=1000.0, help='Min 24h volume USD per pair (default: 1000).')
    parser.add_argument('--min-txns-h1', type=int, default=1, help='Min txns (buys + sells) in the last hour (default: 1).')
    parser.add_argument('--interval', type=int, default=60, help='Seconds to wait between each scan (default: 60).')
    parser.add_argument('--min-profit', type=float, default=0.0, help='Minimum net profit in USD required for multi-leg opportunities (default: 0.0).')
    parser.add_argument('--telegram-enabled', action='store_true', help='Enable Telegram notifications.')
    parser.add_argument('--twitter-enabled', action='store_true', help='Enable Twitter notifications.')
    parser.add_argument('--min-tweet-momentum-score', type=float, default=7.0, help='Minimum momentum score required to send a tweet (default: 7.0).')
    parser.add_argument('--alert-cooldown', type=int, default=3600, help='Cooldown in seconds before re-alerting for the same opportunity (default: 3600).')
    parser.add_argument('--scanner-enabled', action='store_true', help='Enable the background arbitrage scanner.')
    parser.add_argument('--disable-ai-analysis', action='store_true', help='Disable AI-generated analysis for alerts and social posts.')

    # --- Multi-Leg Arguments ---
    parser.add_argument('--multi-leg', action='store_true', help='Enable multi-leg (triangular) arbitrage scanning.')
    parser.add_argument('--max-cycle-length', type=int, default=3, help='Max swaps in a multi-leg cycle (default: 3).')
    parser.add_argument('--max-depth', type=int, default=2, help='Max recursion depth for finding token pairs (default: 2).')
    parser.add_argument('--show-momentum', action='store_true', help='Display recent momentum records and exit.')
    parser.add_argument('--momentum-limit', type=int, default=10, help='Number of recent momentum records to display (default: 10).')
    parser.add_argument('--momentum-token', type=str, help='Filter momentum records by token symbol.')
    parser.add_argument('--momentum-direction', choices=['BULLISH', 'BEARISH'], help='Filter momentum records by direction.')
    parser.add_argument('--limit-base-dexes', action='store_true', help='Restrict Base chain scanning to Aerodrome and Uniswap in single-leg modes.')
    parser.add_argument('--integration-test', action='store_true', help='Relax aggressive-mode thresholds for integration testing.')
    parser.add_argument('--auto-trade', action='store_true', help='Enable experimental automated trading for detected opportunities.')
    parser.add_argument('--trade-rpc-url', type=str, help='RPC endpoint used when auto trading is enabled.')
    parser.add_argument('--trade-wallet-address', type=str, help='Optional public wallet address for logging when auto trading.')
    parser.add_argument('--trade-max-slippage', type=float, default=1.0, help='Maximum allowed slippage percentage for auto trades (default: 1.0).')

    args = parser.parse_args()

    if not args.show_momentum and (not args.chain or not args.token):
        parser.error('--chain and --token are required unless --show-momentum is specified.')

    # Load from environment
    etherscan_api_key = os.environ.get(constants.ETHERSCAN_API_KEY_ENV_VAR)
    telegram_bot_token = os.environ.get(constants.TELEGRAM_BOT_TOKEN_ENV_VAR)
    telegram_chat_id = os.environ.get(constants.TELEGRAM_CHAT_ID_ENV_VAR)
    coingecko_api_key = os.environ.get(constants.COINGECKO_API_KEY_ENV_VAR)
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    twitter_api_key = os.environ.get(constants.TWITTER_API_KEY_ENV_VAR)
    twitter_api_secret = os.environ.get(constants.TWITTER_API_SECRET_ENV_VAR)
    twitter_access_token = os.environ.get(constants.TWITTER_ACCESS_TOKEN_ENV_VAR)
    twitter_access_token_secret = os.environ.get(constants.TWITTER_ACCESS_TOKEN_SECRET_ENV_VAR)

    ai_analysis_env = os.environ.get(constants.AI_ANALYSIS_ENABLED_ENV_VAR)
    ai_analysis_enabled = not args.disable_ai_analysis
    if ai_analysis_env is not None:
        ai_analysis_enabled = ai_analysis_env.lower() not in {"0", "false", "no", "off"}

    if not etherscan_api_key and not args.show_momentum:
        print(f"{constants.C_RED}{constants.ETHERSCAN_API_KEY_ENV_VAR} environment variable not set. Get it from https://etherscan.io/apis{constants.C_RESET}")
        exit(1)

    if args.telegram_enabled and not (telegram_bot_token and telegram_chat_id):
        print(f"{constants.C_RED}Telegram is enabled, but {constants.TELEGRAM_BOT_TOKEN_ENV_VAR} or {constants.TELEGRAM_CHAT_ID_ENV_VAR} are not set.{constants.C_RESET}")
        exit(1)

    if args.twitter_enabled and not (twitter_api_key and twitter_api_secret and twitter_access_token and twitter_access_token_secret):
        print(f"{constants.C_RED}Twitter is enabled, but one or more Twitter API environment variables are not set.{constants.C_RESET}")
        exit(1)

    trading_private_key = os.environ.get('TRADING_PRIVATE_KEY')
    if args.auto_trade:
        if not args.trade_rpc_url:
            print(f"{constants.C_RED}--auto-trade requires --trade-rpc-url to be specified.{constants.C_RESET}")
            exit(1)
        if not trading_private_key:
            print(f"{constants.C_RED}TRADING_PRIVATE_KEY environment variable not set; required for --auto-trade.{constants.C_RESET}")
            exit(1)

    return AppConfig(
        chains=args.chain or [],
        tokens=args.token or [],
        dex_fee=args.dex_fee,
        slippage=args.slippage,
        min_bullish_profit=args.min_bullish_profit,
        min_bearish_discrepancy=args.min_bearish_discrepancy,
        min_momentum_score_bullish=args.min_momentum_score_bullish,
        min_momentum_score_bearish=args.min_momentum_score_bearish,
        trade_volume=args.trade_volume,
        min_liquidity=args.min_liquidity,
        min_volume=args.min_volume,
        min_txns_h1=args.min_txns_h1,
        interval=args.interval,
        min_profit=args.min_profit,
        telegram_enabled=args.telegram_enabled,
        twitter_enabled=args.twitter_enabled,
        min_tweet_momentum_score=args.min_tweet_momentum_score,
        alert_cooldown=args.alert_cooldown,
        etherscan_api_key=etherscan_api_key or "",
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        coingecko_api_key=coingecko_api_key,
        gemini_api_key=gemini_api_key,
        ai_analysis_enabled=ai_analysis_enabled,
        twitter_api_key=twitter_api_key,
        twitter_api_secret=twitter_api_secret,
        twitter_access_token=twitter_access_token,
        twitter_access_token_secret=twitter_access_token_secret,
        multi_leg=args.multi_leg,
        max_cycle_length=args.max_cycle_length,
        max_depth=args.max_depth,
        scanner_enabled=args.scanner_enabled,
        show_momentum=args.show_momentum,
        momentum_limit=args.momentum_limit,
        momentum_token=args.momentum_token.upper() if args.momentum_token else None,
        momentum_direction=args.momentum_direction,
        limit_base_dexes=args.limit_base_dexes,
        integration_test=args.integration_test,
        auto_trade=args.auto_trade,
        trade_rpc_url=args.trade_rpc_url,
        trade_wallet_address=args.trade_wallet_address,
        trade_max_slippage=args.trade_max_slippage,
        trading_private_key=trading_private_key,
    )
