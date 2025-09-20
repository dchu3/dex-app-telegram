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
echo "🚀 Starting DEX Momentum Signal Bot (simple mode)..."
python main.py \
  --chain base \
  --token BRETT ZORA VIRTUAL AERO AVNT CBBTC WETH SAPIEN RFG MIRROR SOSO PIKACHU BIO AUBRAI KTA DINO EDGE BID HYPE FACY GIZA RETAKE REI FLOCK MAMO AIXBT DEGEN VVV TOSHI AAVE \
  --scanner-enabled \
  --telegram-enabled \
  --trade-volume 2000 \
  --dex-fee 0.3 \
  --slippage 0.4 \
  --min-bullish-profit 5 \
  --min-bearish-discrepancy 1.5 \
  --min-momentum-score-bullish 3 \
  --min-momentum-score-bearish 3 \
  --min-liquidity 400000 \
  --min-volume 600000 \
  --min-txns-h1 3 \
  --interval 20 \
  --alert-cooldown 1800 \
  --disable-ai-analysis
