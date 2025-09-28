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
INTEGRATION_TEST=false
NO_AI=false
ENABLE_TWITTER=false
ENABLE_ONCHAIN=false
ONCHAIN_RPC_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --integration-test)
      INTEGRATION_TEST=true
      ;;
    --no-ai)
      NO_AI=true
      ;;
    --enable-twitter)
      ENABLE_TWITTER=true
      ;;
    --disable-twitter)
      ENABLE_TWITTER=false
      ;;
    --enable-onchain-validation)
      ENABLE_ONCHAIN=true
      ;;
    --onchain-validation-rpc-url)
      if [[ -z "$2" ]]; then
        echo "Missing value for --onchain-validation-rpc-url"
        exit 1
      fi
      ONCHAIN_RPC_URL="$2"
      shift
      ;;
    *)
      echo "Unknown flag: $1"
      exit 1
      ;;
  esac
  shift
done

MIN_LIQUIDITY=50000
MIN_VOLUME=100000
MIN_SCORE=2
MIN_BULLISH_PROFIT=0.75
MIN_BEARISH_DISCREP=0.75
EXTRA_FLAGS=("--limit-base-dexes")

if [[ "$INTEGRATION_TEST" == true ]]; then
  echo "⚙️  Integration test thresholds applied."
  MIN_LIQUIDITY=20000
  MIN_VOLUME=50000
  MIN_SCORE=0
  MIN_BULLISH_PROFIT=0.5
  MIN_BEARISH_DISCREP=0.5
  EXTRA_FLAGS+=("--integration-test")
fi

if [[ "$NO_AI" == true ]]; then
  echo "🔇 AI analysis disabled for this run."
  EXTRA_FLAGS+=("--disable-ai-analysis")
fi

if [[ "$ENABLE_TWITTER" == true ]]; then
  EXTRA_FLAGS+=("--twitter-enabled")
fi

if [[ "$ENABLE_ONCHAIN" == true ]]; then
  EXTRA_FLAGS+=("--enable-onchain-validation")
  if [[ -n "$ONCHAIN_RPC_URL" ]]; then
    EXTRA_FLAGS+=("--onchain-validation-rpc-url" "$ONCHAIN_RPC_URL")
  fi
fi

# Run the bot with single-leg arbitrage defaults
echo "🚀 Starting DEX Momentum Signal Bot (aggressive mode)..."
python main.py \
  --chain base \
  --token BRETT ZORA VIRTUAL AERO AVNT CBBTC WETH  AAVE PENDLE \
  --scanner-enabled \
  --telegram-enabled \
  --trade-volume 250 \
  --dex-fee 0.3 \
  --slippage 0.5 \
  --min-bullish-profit ${MIN_BULLISH_PROFIT} \
  --min-bearish-discrepancy ${MIN_BEARISH_DISCREP} \
  --min-momentum-score-bullish ${MIN_SCORE} \
  --min-momentum-score-bearish ${MIN_SCORE} \
  --min-liquidity ${MIN_LIQUIDITY} \
  --min-volume ${MIN_VOLUME} \
  --min-txns-h1 100 \
  --interval 30 \
  --alert-cooldown 900 \
  ${EXTRA_FLAGS[@]}
