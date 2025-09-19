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
# export GEMINI_API_KEY="YourGeminiKey"

# Run the bot with default options
echo "🚀 Starting DEX Momentum Signal Bot..."
python main.py \
  --chain base \
  --token BRETT ZORA VIRTUAL AERO AVNT AAVE \
  --multi-leg \
  --max-cycle-length 3 \
  --max-depth 1 \
  --scanner-enabled \
  --telegram-enabled \
  --trade-volume 1500 \
  --dex-fee 0.3 \
  --slippage 0.4 \
  --min-liquidity 750000 \
  --min-volume 1000000 \
  --min-txns-h1 4 \
  --interval 240 \
  --alert-cooldown 2400 \
  --min-profit 15 \
  --disable-ai-analysis
