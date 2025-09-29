#!/usr/bin/env python3
import asyncio
import aiohttp
import time
from datetime import datetime, time as dt_time, timezone
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TimedOut, TelegramError

import constants
from config import load_config
from bot.handlers import (
    help_command,
    status_command,
    trending_command,
    market_command,
    scaninfo_command,
)
from scanner import ArbitrageScanner
from services.dexscreener_client import DexScreenerClient
from services.etherscan_client import EtherscanClient
from services.coingecko_client import CoinGeckoClient
from services.blockscout_client import BlockscoutClient
from services.geckoterminal_client import GeckoTerminalClient
from services.gemini_client import GeminiClient
from services.twitter_client import TwitterClient
from services.trade_executor import TradeExecutor
from services.onchain_price_validator import OnChainPriceValidator
from storage import SQLiteRepository
from reports.base_daily_summary import BaseDailySummaryBuilder

async def post_init_hook(application: Application) -> None:
    """A hook that runs after the bot is initialized to set up shared clients and tasks."""
    # Create and store a single, shared aiohttp session
    session = aiohttp.ClientSession(headers={'User-Agent': 'DexAppBot/1.0'})
    application.bot_data['http_session'] = session

    # Initialize and store clients
    config = application.bot_data['config']
    coingecko_client = CoinGeckoClient(session, config.coingecko_api_key)
    application.bot_data['coingecko_client'] = coingecko_client
    application.bot_data['dexscreener_client'] = DexScreenerClient(session, coingecko_client)
    application.bot_data['etherscan_client'] = EtherscanClient(session, config.etherscan_api_key)
    application.bot_data['blockscout_client'] = BlockscoutClient(session)
    application.bot_data['geckoterminal_client'] = GeckoTerminalClient(session)
    gemini_client = None
    if config.ai_analysis_enabled and config.gemini_api_key:
        gemini_client = GeminiClient(session, config.gemini_api_key)
    application.bot_data['gemini_client'] = gemini_client

    # Initialize Twitter client if enabled
    twitter_client = None
    if config.twitter_enabled:
        try:
            twitter_client = TwitterClient(config)
            print("Twitter client initialized.")
        except ValueError as e:
            print(f"Could not initialize Twitter client: {e}")
    application.bot_data['twitter_client'] = twitter_client

    trade_executor = None
    if config.auto_trade:
        try:
            trade_executor = TradeExecutor(
                rpc_url=config.trade_rpc_url,
                private_key=config.trading_private_key,
                wallet_address=config.trade_wallet_address,
                max_slippage_pct=config.trade_max_slippage,
            )
            print("Trade executor initialized.")
        except Exception as exc:
            print(f"{constants.C_RED}Failed to initialise trade executor: {exc}{constants.C_RESET}")
            exit(1)
    application.bot_data['trade_executor'] = trade_executor

    onchain_validator = None
    if config.onchain_validation_enabled:
        if not config.onchain_validation_rpc_url:
            print(
                f"{constants.C_YELLOW}On-chain validation enabled but no RPC URL provided; falling back to API prices only.{constants.C_RESET}"
            )
        else:
            try:
                onchain_validator = OnChainPriceValidator(
                    session,
                    rpc_url=config.onchain_validation_rpc_url,
                    max_pct_diff=config.onchain_validation_max_pct_diff,
                    timeout=config.onchain_validation_timeout,
                    common_token_addresses=constants.COMMON_TOKEN_ADDRESSES,
                )
                print("On-chain price validator initialised.")
            except Exception as exc:
                print(
                    f"{constants.C_RED}Failed to initialise on-chain validator: {exc}. Continuing without validation.{constants.C_RESET}"
                )
                onchain_validator = None
    application.bot_data['onchain_validator'] = onchain_validator

    # Set bot commands
    commands = [
        BotCommand("status", "Check bot status"),
        BotCommand("trending", "Get trending coins"),
        BotCommand("market", "Get global market snapshot"),
        BotCommand("scaninfo", "See current scan config"),
        BotCommand("help", "Show help message"),
    ]
    try:
        await application.bot.set_my_commands(commands)
    except (TimedOut, TelegramError) as exc:
        print(
            f"{constants.C_YELLOW}Warning: unable to set Telegram bot commands ({exc})."
            f" Continuing startup without updating commands.{constants.C_RESET}"
        )

    # Prepare daily summary builder & schedule
    if config.daily_summary_enabled:
        repository = application.bot_data.get('repository')
        geckoterminal_client = application.bot_data.get('geckoterminal_client')
        if repository and geckoterminal_client:
            summary_builder = BaseDailySummaryBuilder(
                repository=repository,
                geckoterminal_client=geckoterminal_client,
                coingecko_client=coingecko_client,
            )
            application.bot_data['base_daily_summary_builder'] = summary_builder
            application.bot_data['daily_summary_tweet_enabled'] = config.daily_summary_tweet_enabled
            if application.job_queue:
                application.job_queue.run_daily(
                    run_base_daily_summary,
                    time=dt_time(hour=8, minute=0, tzinfo=timezone.utc),
                    name="base-daily-summary",
                )
        else:
            print(
                f"{constants.C_YELLOW}Daily summary enabled but repository or GeckoTerminal client missing; skipping schedule.{constants.C_RESET}"
            )

    # Start scanner task if enabled
    if config.scanner_enabled:
        scanner = ArbitrageScanner(
            config,
            application,
            application.bot_data['dexscreener_client'],
            application.bot_data['etherscan_client'],
            application.bot_data['coingecko_client'],
            application.bot_data['blockscout_client'],
            application.bot_data['gemini_client'],
            application.bot_data['twitter_client'],
            application.bot_data.get('repository'),
            application.bot_data.get('trade_executor'),
            application.bot_data.get('onchain_validator'),
        )
        scanner_task = asyncio.create_task(scanner.start())
        application.bot_data['scanner_task'] = scanner_task

async def post_shutdown_hook(application: Application) -> None:
    """A hook that runs on application shutdown to clean up resources."""
    session = application.bot_data.get('http_session')
    if session:
        await session.close()
    repository = application.bot_data.get('repository')
    if repository:
        await repository.close()
    executor = application.bot_data.get('trade_executor')
    if executor:
        await executor.close()


async def run_base_daily_summary(context: ContextTypes.DEFAULT_TYPE) -> None:
    application = context.application
    config = application.bot_data.get('config')
    builder: BaseDailySummaryBuilder | None = application.bot_data.get('base_daily_summary_builder')
    if not builder or not config:
        return

    try:
        result = await builder.build()
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"{constants.C_RED}Daily summary generation failed: {exc}{constants.C_RESET}")
        return

    if not result.has_content:
        print("Daily summary skipped: no qualifying Base momentum records in the last 24h.")
        return

    tweet_text = result.tweet_text
    if not tweet_text:
        return

    twitter_client: TwitterClient | None = application.bot_data.get('twitter_client')
    tweet_enabled = (
        config.twitter_enabled
        and config.daily_summary_tweet_enabled
        and twitter_client is not None
        and application.bot_data.get('daily_summary_tweet_enabled', False)
    )

    if tweet_enabled:
        try:
            twitter_client.post_tweet(tweet_text)
            print(f"{constants.C_GREEN}Daily Base summary tweet sent at {datetime.now(timezone.utc).isoformat()}{constants.C_RESET}")
        except Exception as exc:  # pragma: no cover - network dependent
            print(f"{constants.C_RED}Failed to post daily summary tweet: {exc}{constants.C_RESET}")
    else:
        print("Daily summary tweet ready (disabled):\n" + tweet_text)

def main() -> None:
    """The main synchronous entry point for the application."""
    config = load_config()

    if config.show_momentum:
        repository = SQLiteRepository()
        try:
            records = asyncio.run(
                repository.fetch_momentum_records(
                    limit=config.momentum_limit,
                    token=config.momentum_token,
                    direction=config.momentum_direction,
                )
            )
        finally:
            asyncio.run(repository.close())
        _print_momentum_records(records, config.momentum_limit, config.momentum_token, config.momentum_direction)
        return

    repository = SQLiteRepository()

    if not config.telegram_enabled or not config.telegram_bot_token:
        print("Telegram is not configured. The application will run in CLI-only mode.")

    application = (
        Application.builder()
        .token(config.telegram_bot_token)
        .post_init(post_init_hook)
        .post_shutdown(post_shutdown_hook)
        .build()
    )

    # Store config and other shared data
    application.bot_data['config'] = config
    application.bot_data['start_time'] = time.time()
    application.bot_data['scan_info'] = {
        'chains': config.chains,
        'tokens': config.tokens,
    }
    application.bot_data['repository'] = repository
    application.bot_data['trade_executor'] = None

    # Register command handlers
    application.add_handler(CommandHandler("start", help_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("trending", trending_command))
    application.add_handler(CommandHandler("market", market_command))
    application.add_handler(CommandHandler("scaninfo", scaninfo_command))

    application.run_polling()




def _print_momentum_records(records: list[dict], limit: int, token: str | None, direction: str | None) -> None:
    heading = f"Showing up to {limit} momentum records"
    filters = []
    if token:
        filters.append(f"token={token.upper()}")
    if direction:
        filters.append(f"direction={direction}")
    if filters:
        heading += " (" + ", ".join(filters) + ")"
    print(heading)
    print("=" * len(heading))

    if not records:
        print("No momentum records found.")
        return

    headers = [
        "Time (UTC)",
        "Token",
        "Spread %",
        "Score",
        "Net $",
        "Clip $",
        "Flow Skew",
        "Trend 1h",
        "Vol5m %",
        "Tx5m",
        "Early",
    ]

    def _format_percent(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:+.2f}%"

    def _format_flow(record: dict) -> str:
        ratio = record.get("dominant_volume_ratio")
        side = record.get("flow_side")
        if ratio and ratio > 0 and side:
            return f"{side.capitalize()} {ratio:.2f}x"
        if side:
            return side.capitalize()
        return "-"

    def _format_trend(record: dict) -> str:
        parts = []
        trend_buy = record.get("trend_buy_change_h1")
        trend_sell = record.get("trend_sell_change_h1")
        if trend_buy is not None:
            parts.append(f"Buy {_format_percent(trend_buy)}")
        if trend_sell is not None:
            parts.append(f"Sell {_format_percent(trend_sell)}")
        return " / ".join(parts) if parts else "-"

    def _format_row(record: dict) -> list[str]:
        alert_time: datetime = record.get("alert_time")
        time_str = alert_time.strftime("%Y-%m-%d %H:%M:%S") if alert_time else "N/A"
        spread = record.get("spread_pct")
        vol_ratio = record.get("short_term_volume_ratio")
        clip = record.get("effective_volume_usd")
        txns = record.get("short_term_txns_total")
        txns_str = str(txns) if txns is not None else "-"
        return [
            time_str,
            record.get("token", ""),
            f"{spread:.2f}" if spread is not None else "-",
            f"{record.get('momentum_score', 0.0):.1f}",
            f"{record.get('net_profit_usd', 0.0):.2f}",
            f"{clip:,.0f}" if clip is not None else "-",
            _format_flow(record),
            _format_trend(record),
            f"{vol_ratio * 100:.1f}" if vol_ratio is not None else "-",
            txns_str,
            "Yes" if record.get("is_early_momentum") else "No",
        ]

    rows = [_format_row(rec) for rec in records]
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def _format_line(row: list[str]) -> str:
        return "  ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))

    print(_format_line(headers))
    print("  ".join('-' * w for w in widths))
    for row in rows:
        print(_format_line(row))


if __name__ == "__main__":
    main()
