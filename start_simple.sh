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

# Detect optional flags
ENABLE_TWITTER=false
ENABLE_SIGNAL_TWEETS=false
ENABLE_DAILY_SUMMARY=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --enable-twitter)
      ENABLE_TWITTER=true
      ;;
    --disable-twitter)
      ENABLE_TWITTER=false
      ;;
    --enable-signal-tweets)
      ENABLE_SIGNAL_TWEETS=true
      ;;
    --disable-daily-summary)
      ENABLE_DAILY_SUMMARY=false
      ;;
    *)
      echo "Unknown flag: $1"
      exit 1
      ;;
  esac
  shift
done

# Run the bot with single-leg arbitrage defaults
echo "🚀 Starting DEX Momentum Signal Bot (simple mode)..."
CMD=(
  python main.py
  --chain base
  --token BRETT ZORA VIRTUAL AERO AVNT CBBTC WETH SAPIEN RFG MIRROR SOSO PIKACHU BIO AUBRAI KTA DINO EDGE BID HYPE FACY GIZA RETAKE REI FLOCK MAMO AIXBT DEGEN VVV TOSHI AAVE SPX KEYCAT PENGU
  --scanner-enabled
  --telegram-enabled
  --trade-volume 500
  --dex-fee 0.3
  --slippage 0.4
  --min-bullish-profit 1.0
  --min-bearish-discrepancy 1.0
  --min-momentum-score-bullish 3
  --min-momentum-score-bearish 3
  --min-liquidity 400000
  --min-volume 50000
  --min-txns-h1 3
  --interval 20
  --alert-cooldown 1800
  --limit-base-dexes
)

if [[ "$ENABLE_DAILY_SUMMARY" == true ]]; then
  CMD+=(--daily-summary-enabled)
fi

if [[ "$ENABLE_TWITTER" == true ]]; then
  CMD+=(--twitter-enabled)
  CMD+=(--daily-summary-tweet-enabled)
  if [[ "$ENABLE_SIGNAL_TWEETS" == true ]]; then
    CMD+=(--signal-tweets-enabled)
  fi
else
  if [[ "$ENABLE_SIGNAL_TWEETS" == true ]]; then
    echo "⚠️  Signal tweets require Twitter to be enabled; ignoring --enable-signal-tweets." >&2
  fi
  echo "ℹ️  Twitter disabled; no social posts will be attempted."
fi

"${CMD[@]}"
