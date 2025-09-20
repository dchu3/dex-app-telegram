#!/usr/bin/env python3
import asyncio
import aiohttp
import time
from telegram import BotCommand
from telegram.ext import Application, CommandHandler

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
from services.gemini_client import GeminiClient
from services.twitter_client import TwitterClient
from storage import SQLiteRepository

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

    # Set bot commands
    commands = [
        BotCommand("status", "Check bot status"),
        BotCommand("trending", "Get trending coins"),
        BotCommand("market", "Get global market snapshot"),
        BotCommand("scaninfo", "See current scan config"),
        BotCommand("help", "Show help message"),
    ]
    await application.bot.set_my_commands(commands)

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
            application.bot_data.get('repository')
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

def main() -> None:
    """The main synchronous entry point for the application."""
    config = load_config()

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

    # Register command handlers
    application.add_handler(CommandHandler("start", help_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("trending", trending_command))
    application.add_handler(CommandHandler("market", market_command))
    application.add_handler(CommandHandler("scaninfo", scaninfo_command))

    application.run_polling()


if __name__ == "__main__":
    main()
