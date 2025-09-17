# Repository Guidelines

## Project Structure & Module Organization
Runtime orchestration lives in `main.py`, which wires the Telegram bot, config loader, and `ArbitrageScanner`. Signal evaluation is handled in `scanner.py`, delegating pricing maths to `analysis/analyzer.py` and multi-leg logic in `analysis/multi_leg_analyzer.py`. API adapters sit under `services/` (DexScreener, Etherscan, CoinGecko, Gemini, Twitter), while chat handlers are grouped in `bot/`. Shared constants, scoring helpers, and CLI setup are defined in `constants.py`, `momentum_indicator.py`, and `config.py`. Tests mirror this layout inside `tests/`, separated into `analysis/` and `services/` suites.

## Build, Test, and Development Commands
Use `./setup.sh` for the fastest bootstrap of the virtualenv and production dependencies. For manual installs run `pip install -r requirements.txt`. Launch the scanner or bot locally with `python main.py --chain base --token AERO --telegram-enabled --scanner-enabled`. Execute the full regression suite via `pytest`. Focus a single case with `pytest tests/analysis/test_analyzer.py -k bullish` when iterating on signal logic.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation and snake_case identifiers for functions, modules, and async tasks. Keep public call signatures typed; new helpers should return dataclasses or NamedTuples similar to `AppConfig`. Prefer descriptive module-level constants to raw literals, and extend existing dictionaries in `constants.py` instead of scattering config flags.

## Testing Guidelines
Write unit coverage beside the feature under `tests/`, using `pytest-asyncio` markers for coroutine behaviour. Mimic existing naming such as `test_scanner.py::test_process_bullish_opportunity`—use `test_<subject>_<expectation>` for clarity. Update fixtures when adding new environment flags, and ensure multi-chain scenarios include representative sample payloads. Run `pytest` before each push and attach terminal output to the PR when failures occur.

## Commit & Pull Request Guidelines
Commit messages should stay in the imperative mood and scoped to one change set (e.g., `feat: refine bearish momentum filter`). Reference related issues in the body when applicable. Pull requests need a short summary, testing notes, and screenshots or sample payloads for Telegram alerts whenever UI-facing output changes. Flag config migrations and breaking API updates explicitly.

## Security & Configuration Tips
API keys are loaded from environment variables in `config.py`; never commit them or default secrets. Sanity-check rate limits when adjusting polling intervals to protect upstream providers. When sharing logs, redact token addresses or telegram chat IDs from the console output.
