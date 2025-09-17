## Project Overview

This project is a Python-based command-line tool and interactive Telegram bot that identifies potential market momentum signals by analyzing price discrepancies on decentralized exchanges (DEXs). It concurrently scans for price differences of given cryptocurrencies across multiple DEXs on multiple blockchains (such as Ethereum, Polygon, and Base).

When a significant signal is detected, the bot sends a Telegram alert containing an AI-generated analysis and a hypothetical stop-limit trading plan. The project is built with `asyncio` for asynchronous operations and uses several external APIs for data collection:

*   **DexScreener:** For DEX pair data.
*   **Etherscan/Blockscout:** For gas price information.
*   **CoinGecko:** For live RSI data.
*   **Gemini:** For AI-powered analysis of trading signals.

## Building and Running

### Prerequisites

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### API and Bot Configuration

The application requires API keys for several services. These should be set as environment variables:

*   **Etherscan API Key:**
    ```bash
    export ETHERSCAN_API_KEY='YourApiKeyHere'
    ```
*   **Telegram Bot Token and Chat ID:**
    ```bash
    export TELEGRAM_BOT_TOKEN='YourBotToken'
    export TELEGRAM_CHAT_ID='YourChatID'
    ```
*   **CoinGecko API Key:**
    ```bash
    export COINGECKO_API_KEY='YourCoinGeckoApiKey'
    ```
*   **Gemini API Key:**
    ```bash
    export GEMINI_API_KEY='YourGeminiApiKeyHere'
    ```

### Running the Application

Run the script from your terminal. To stop the script, press `Ctrl+C`.

**Example:**

```bash
python main.py --chain base --token AERO --telegram-enabled --scanner-enabled
```

### Command-Line Arguments

*   `--chain`: One or more blockchains to scan. Required.
*   `--token`: One or more token symbols to search for. Required.
*   `--interval`: Seconds to wait between each scan cycle. Default: `60`.
*   `--telegram-enabled`: Flag to enable the Telegram bot.
*   `--scanner-enabled`: Flag to enable the background scanner.
*   `--min-profit`: Minimum profit percentage to consider a signal. Default: `0.0`.

## Development Conventions

*   **Configuration:** The application is configured through a combination of command-line arguments and environment variables. The `config.py` file uses the `argparse` library to define and parse command-line arguments, and `os.environ.get` to load secrets from environment variables.
*   **Asynchronous Operations:** The project heavily relies on `asyncio` and `aiohttp` for concurrent and non-blocking network requests.
*   **Modularity:** The codebase is organized into several modules:
    *   `bot`: Contains Telegram bot handlers.
    *   `services`: Contains clients for interacting with external APIs.
    *   `analysis`: Contains logic for analyzing arbitrage opportunities.
*   **Entry Point:** The main entry point of the application is `main.py`, which initializes the configuration, sets up the Telegram bot, and starts the scanner.
*   **Error Handling:** The main scan cycle in `scanner.py` includes a `try...except` block to catch and log errors, preventing the application from crashing.
