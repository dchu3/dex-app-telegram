# DEX Momentum Signal Bot

This Python script is a command-line tool and interactive Telegram bot that identifies potential market momentum signals by analyzing price discrepancies on decentralized exchanges (DEXs).

## Features

- **Momentum Signal Generation:** Identifies price discrepancies and reframes them as actionable momentum signals.
- **Early Momentum Heuristics:** Uses 5-minute volume and transaction spikes to surface emerging moves even before deep liquidity builds.
- **Base DEX Guardrails:** When running the single-leg scanners on Base, opportunities are restricted to Aerodrome ↔ Uniswap pairs to avoid thin venues.
- **Multi-Leg (Triangular) Arbitrage Scanning:** In addition to direct discrepancies, the bot can identify triangular arbitrage opportunities involving three tokens.
- **Structured AI-Powered Analysis:** Integrates with Google's Gemini AI to provide a detailed, structured analysis for each signal, covering:
    - **AI Thesis:** A concise summary of the signal.
    - **Market Sentiment:** An analysis of the current market sentiment for the token.
    - **Key Drivers:** Factors driving the price discrepancy and momentum.
    - **Potential Risks:** Potential risks associated with the signal. This AI step can be disabled at runtime with `--disable-ai-analysis` or by setting `AI_ANALYSIS_ENABLED=0`.
- **Quantitative Momentum Score:** Calculates a momentum score (0-10) for each signal based on:
    - **Volume Divergence:** The ratio of 24h trading volume between the two DEXs.
    - **Signal Persistence:** How many times the same opportunity has been detected recently.
    - **Live RSI Data:** The 14-day Relative Strength Index (RSI) fetched from CoinGecko.
- **Concurrent Multi-Chain Scanning:** Scans multiple blockchains like `ethereum`, `polygon`, and `base` at the same time.
- **Interactive Telegram Bot:** A streamlined set of commands for monitoring the bot and the market:
    - `/status`: Get a real-time report of the bot's operational status, uptime, and scanner activity.
    - `/trending`: Get the top-7 trending coins from CoinGecko.
    - `/market`: Get a snapshot of the global crypto market.
    - `/scaninfo`: See the current chains and tokens being scanned.
    - `/help`: Display a list of all available commands.
- **Multi-Source Data:** Uses a combination of DexScreener, Etherscan, Blockscout (for Base chain), and CoinGecko to ensure data accuracy and reliability.
- **Asynchronous & Robust:** Uses `asyncio` and `aiohttp` for efficient, non-blocking network requests with proper rate-limiting.
- **Configurable:** Allows users to set various parameters such as chains, tokens, scan interval, and profitability thresholds.
- **Twitter Integration:** Optionally post generated signals to a configured Twitter account.
- **Optional Auto-Trade:** Experimental hook can prepare Aerodrome ↔ Uniswap swaps when enabled.

## How It Works

1.  **Initialization:** The script parses command-line arguments and environment variables to configure the bot and scanner.
2.  **Bot Startup:** It launches the Telegram bot, which listens for user commands.
3.  **Scanner Task:** If enabled, it starts the scanner as a background task.
4.  **Data Fetching & Analysis:** The scanner fetches pair data from DexScreener and gas prices from Etherscan/Blockscout to identify significant price discrepancies.
5.  **Momentum Scoring:** For each valid discrepancy, a momentum score is calculated using live RSI from CoinGecko, volume divergence, and signal persistence.
6.  **AI Analysis Generation:** The signal data is sent to the Gemini AI, which generates a structured, human-readable analysis for the momentum signal.
7.  **Alert Generation:** A Telegram alert is constructed, containing the detailed signal data and the AI-generated analysis.
8.  **On-Demand Commands (Bot):** The bot responds to user commands by fetching data from the appropriate API and returning formatted results.

## Scripts

### `setup.sh`

This script automates the project setup. It creates a Python virtual environment and installs all the required dependencies from `requirements.txt`.

```
./setup.sh
```

### `start.sh`

Launches the bot with the multi-leg (triangular) Base-chain profile tuned for DexScreener limits. Update the flags inside if you want a different chain, interval, or profit floor.

```
./start.sh
```

### `start_simple.sh`

Runs the single-leg scanner with slightly tighter liquidity filters and faster polling so you can compare results without multi-leg routing.

Base-chain scans are limited to Aerodrome/Uniswap to ensure sufficient depth.

```
./start_simple.sh
```

## Data Persistence

Momentum alerts that pass the Telegram filters are archived in `data/momentum_history.db`, a lightweight SQLite database created on startup. Each entry stores the opportunity snapshot alongside the short-term momentum breakdown (volume divergence, persistence, RSI, 5-minute surge stats), making it easy to analyse historical signals or adapt thresholds later. Delete the file if you want a clean slate; it is recreated automatically.

### CLI: Show Momentum History

Inspect the latest alerts directly from the command line without launching the bot:

```
python main.py --show-momentum --momentum-limit 20
```

### Aggressive Mode Integration Test

Run `./start_aggressive.sh --integration-test` to enable relaxed liquidity/volume thresholds and keep AI copy on—ideal for validating the pipeline against thinner Base liquidity. Add `--no-ai` if you need to silence Gemini output during tests.

### Automated Trading (Experimental)

To exercise the scaffolded trade executor:

1. Export `TRADING_PRIVATE_KEY` with the funded wallet key.
2. Launch with `--auto-trade --trade-rpc-url <Base RPC URL>` plus your usual scanner flags.
3. Optional knobs: `--trade-wallet-address` (for logging) and `--trade-max-slippage <percent>` (default 1.0).

The current implementation converts USD exposure into token amounts and logs the intended Aerodrome ↔ Uniswap trade; extend `services/trade_executor.py` with router calls when you are ready to submit live transactions.

## Running the Application

### Prerequisites

You will need to install the required Python packages. You can do this manually or by using the `setup.sh` script.

```
pip install -r requirements.txt
```

### API and Bot Configuration

1.  **Etherscan API Key:**
    -   Obtain a free API key from [https://etherscan.io/apis](https://etherscan.io/apis).
    -   Set it as an environment variable: `export ETHERSCAN_API_KEY='YourApiKeyHere'`

2.  **Telegram Bot:**
    -   Create a bot with `BotFather` on Telegram to get a **Bot Token**.
    -   Get your **Chat ID** from a bot like `@userinfobot`.
    -   Set both as environment variables: `export TELEGRAM_BOT_TOKEN='YourBotToken'` and `export TELEGRAM_CHAT_ID='YourChatID'`.

3.  **CoinGecko API Key (Recommended):**
    -   For live RSI data, a CoinGecko API key is highly recommended.
    -   Obtain a free API key from [CoinGecko](https://www.coingecko.com/en/api).
    -   Set it as an environment variable: `export COINGECKO_API_KEY='YourCoinGeckoApiKey'`

4.  **Gemini API Key (Recommended for AI Analysis):**
    -   Obtain a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
    -   Set it as an environment variable: `export GEMINI_API_KEY='YourGeminiApiKeyHere'`
    -   To temporarily suspend AI output, either export `AI_ANALYSIS_ENABLED=0` or pass `--disable-ai-analysis` when launching the bot.

5.  **Twitter API Keys (Optional):**
    -   To enable posting signals to Twitter, you need a Twitter Developer account with a project and an app.
    -   Generate the following credentials from your app's dashboard:
        -   API Key and Secret
        -   Access Token and Secret
    -   Set them as environment variables:
        ```bash
        export TWITTER_API_KEY='YourApiKey'
        export TWITTER_API_SECRET='YourApiSecret'
        export TWITTER_ACCESS_TOKEN='YourAccessToken'
        export TWITTER_ACCESS_TOKEN_SECRET='YourAccessTokenSecret'
        ```

6.  **Trading Private Key (Optional):**
    -   Required only when using `--auto-trade`.
    -   Set it as an environment variable: `export TRADING_PRIVATE_KEY='0xYourPrivateKey'`
    -   Never commit private keys to source control.

### Manual Execution

Run the script from your terminal. To stop the script, press `Ctrl+C`.

#### Example

```
python main.py --chain base --token AERO --telegram-enabled --scanner-enabled
```

### Command-Line Arguments

-   `--chain`: One or more blockchains to scan. Required.
-   `--token`: One or more token symbols to search for. Required.
-   `--dex-fee`: DEX fee percentage (default: 0.3).
-   `--slippage`: Slippage tolerance percentage (default: 0.5).
-   `--min-bullish-profit`: Minimum net profit in USD for a bullish signal (default: 0.0).
-   `--min-bearish-discrepancy`: Minimum price discrepancy percentage for a bearish signal (default: 1.0).
-   `--min-momentum-score-bullish`: Minimum momentum score (0-10) required to trigger a bullish alert (default: 0.0).
-   `--min-momentum-score-bearish`: Minimum momentum score (0-10) required to trigger a bearish alert (default: 0.0).
-   `--trade-volume`: Trade volume in USD for estimates (default: 500).
-   `--min-liquidity`: Min USD liquidity per pair (default: 1000).
-   `--min-volume`: Min 24h volume USD per pair (default: 1000).
-   `--min-txns-h1`: Min txns (buys + sells) in the last hour (default: 1).
-   `--interval`: Seconds to wait between each scan (default: 60).
-   `--min-profit`: Minimum net USD profit required for multi-leg opportunities (default: 0.0).
-   `--telegram-enabled`: Enable Telegram notifications.
-   `--twitter-enabled`: Enable Twitter notifications.
-   `--alert-cooldown`: Cooldown in seconds before re-alerting for the same opportunity (default: 3600).
-   `--scanner-enabled`: Enable the background arbitrage scanner.
-   `--disable-ai-analysis`: Skip Gemini calls and omit AI-generated content from alerts and tweets.
-   `--auto-trade`: Enable experimental automated execution (requires `TRADING_PRIVATE_KEY`).
-   `--trade-rpc-url`: RPC endpoint used when auto trading.
-   `--trade-wallet-address`: Optional public address for on-chain logging.
-   `--trade-max-slippage`: Maximum percentage slippage tolerated when auto trading (default: 1.0).
-   `--multi-leg`: Enable multi-leg (triangular) arbitrage scanning.
-   `--max-cycle-length`: Max swaps in a multi-leg cycle (default: 3).
-   `--max-depth`: Max recursion depth for finding token pairs (default: 2).

## Development

To install the development dependencies, run:

```
pip install -r requirements-dev.txt
```

## Disclaimer

This tool is for educational and informational purposes only and does not constitute financial advice. The signals and analysis generated are based on automated systems. Trading cryptocurrency is highly risky. Always do your own research.
