#!/bin/bash
set -e

# Go to project directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ ! -d "venv" ]; then
  echo "❌ Virtual environment not found. Run ./setup.sh first."
  exit 1
fi
source venv/bin/activate

# --- API KEYS ---
# You can hardcode your keys here, or better, set them in your shell profile (~/.bashrc)
# export ETHERSCAN_API_KEY="YourEtherscanKey"
# export TELEGRAM_BOT_TOKEN="YourTelegramBotToken"
# export TELEGRAM_CHAT_ID="YourTelegramChatID"
# export COINGECKO_API_KEY="YourCoinGeckoKey"

# Run the bot with single-leg arbitrage defaults
echo "🚀 Starting DEX Momentum Signal Bot (aggressive mode)..."
python main.py \
  --chain base \
  --token BRETT ZORA VIRTUAL AERO AVNT CBBTC WETH AAVE \
  --scanner-enabled \
  --telegram-enabled \
  --trade-volume 1000 \
  --dex-fee 0.3 \
  --slippage 0.5 \
  --min-bullish-profit 0.5 \
  --min-bearish-discrepancy 0.5 \
  --min-momentum-score-bullish 2 \
  --min-momentum-score-bearish 2 \
  --min-liquidity 50000 \
  --min-volume 100000 \
  --min-txns-h1 10 \
  --interval 30 \
  --alert-cooldown 900
