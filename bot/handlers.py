# bot/handlers.py
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes
import asyncio
import time
from datetime import datetime

from services.dexscreener_client import DexScreenerClient
from services.etherscan_client import EtherscanClient
from services.coingecko_client import CoinGeckoClient
from config import load_config, AppConfig # Import AppConfig
from scanner import ArbitrageScanner # Import the scanner
from constants import CHAIN_CONFIG # Import CHAIN_CONFIG

# --- Command Handlers ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a help message with all available commands."""
    help_text = """
    <b>Welcome to the DEX Momentum Bot!</b>

    This bot scans for market momentum signals and provides AI-driven analysis.

    <b><u>Available Commands:</u></b>
    /status - Get bot status and last scan info
    /trending - Get top-7 trending coins from CoinGecko
    /market - Get a snapshot of the global crypto market
    /scaninfo - See current scan configuration
    /help - Show this help message
    """
    await update.message.reply_html(help_text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks and reports the bot's operational status and scanner state."""
    config = context.application.bot_data.get('config')
    scanner_task = context.application.bot_data.get('scanner_task')
    start_time = context.application.bot_data.get('start_time', 0)
    
    # Calculate uptime
    uptime_seconds = time.time() - start_time
    uptime_str = time.strftime('%H:%M:%S', time.gmtime(uptime_seconds))

    # Determine scanner status
    scanner_status = ""
    if config and config.scanner_enabled:
        if scanner_task and not scanner_task.done():
            scanner_status = "✅ Running"
        elif scanner_task and scanner_task.done():
            exception = scanner_task.exception()
            if exception:
                scanner_status = f"❌ Stopped with error"
            else:
                scanner_status = "⏹️ Stopped"
        else:
            scanner_status = "⚠️ Enabled but not running"
    else:
        scanner_status = "🚫 Disabled"

    # Build the status message
    status_text = (
        f"<b>🤖 Bot Status</b>\n"
        f"Uptime: <code>{uptime_str}</code>\n\n"
        f"<b>🔍 Scanner</b>\n"
        f"Status: {scanner_status}\n"
    )

    # Add scanner details only if it's enabled
    if config and config.scanner_enabled:
        last_scan = context.application.bot_data.get('last_scan_time', 'Never')
        found_last = context.application.bot_data.get('found_last_scan', 'N/A')
        last_error = context.application.bot_data.get('last_error')

        status_text += f"Last Scan: <code>{last_scan}</code>\n"
        status_text += f"Found Last Scan: <code>{found_last}</code>\n"
        if last_error:
            status_text += f"Last Error: <pre>{last_error}</pre>\n"

    await update.message.reply_html(status_text)

async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the top-7 trending coins from CoinGecko."""
    await update.message.reply_text("Fetching trending coins from CoinGecko...")
    
    client: CoinGeckoClient = context.application.bot_data['coingecko_client']
    
    try:
        trending_coins = await client.get_trending_coins()
        if not trending_coins:
            await update.message.reply_text("Could not fetch trending coins from CoinGecko.")
            return

        response_lines = ["<b>🔥 Top 7 Trending Coins on CoinGecko</b>\n"]
        for coin_data in trending_coins:
            item = coin_data['item']
            line = (
                f"{item['score'] + 1}. <b>{item['name']} ({item['symbol']})</b>\n"
                f"   - Rank: {item['market_cap_rank']}\n"
                f"   - Price (BTC): {item['price_btc']:.8f} ₿"
            )
            response_lines.append(line)
        
        response = "\n".join(response_lines)
        
    except Exception as e:
        print(f"Error in /trending command: {e}")
        response = "An error occurred while fetching trending coins."

    await update.message.reply_html(response)

async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays a snapshot of the global crypto market."""
    await update.message.reply_text("Fetching global market data from CoinGecko...")

    client: CoinGeckoClient = context.application.bot_data['coingecko_client']

    try:
        global_data = await client.get_global_market_data()
        if not global_data or 'data' not in global_data:
            await update.message.reply_text("Could not fetch global market data.")
            return

        data = global_data['data']
        total_mcap = data['total_market_cap'].get('usd', 0)
        total_vol = data['total_volume'].get('usd', 0)
        btc_dom = data['market_cap_percentage'].get('btc', 0)
        eth_dom = data['market_cap_percentage'].get('eth', 0)

        response = (
            f"<b>📊 Global Crypto Market Snapshot</b>\n\n"
            f"<b>Total Market Cap:</b> ${total_mcap:,.0f}\n"
            f"<b>24h Trading Volume:</b> ${total_vol:,.0f}\n\n"
            f"<b>BTC Dominance:</b> {btc_dom:.2f}%\n"
            f"<b>ETH Dominance:</b> {eth_dom:.2f}%"
        )

    except Exception as e:
        print(f"Error in /market command: {e}")
        response = "An error occurred while fetching global market data."

    await update.message.reply_html(response)

async def scaninfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the current chains and tokens being scanned."""
    scan_info = context.application.bot_data.get('scan_info')

    if not scan_info:
        await update.message.reply_text("Scanner configuration not found.")
        return

    chains = ", ".join(scan_info.get('chains', []))
    tokens = ", ".join(scan_info.get('tokens', []))

    message = (
        f"<b>🔍 Current Scanner Configuration</b>\n\n"
        f"<b>Chains:</b> <code>{chains}</code>\n"
        f"<b>Tokens:</b> <code>{tokens}</code>"
    )

    await update.message.reply_html(message)
