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
python main.py --chain base --disable-ai-analysis --telegram-enabled --scanner-enabled --min-momentum-score-bullish 3.0 --min-momentum-score-bearish 3.0 --min-bullish-profit 1.0 --min-liquidity 400000 --min-volume 50000 --min-txns-h1 3 --interval 15 --token BRETT ZORA VIRTUAL AERO CBBTC WETH AVNT
