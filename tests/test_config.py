import argparse
import pytest
from config import load_config, AppConfig

# Mock the os.environ.get to control environment variables during tests
def mock_environ_get(key):
    if key == 'ETHERSCAN_API_KEY':
        return 'mock_etherscan_key'
    return None

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setattr('os.environ.get', mock_environ_get)

def test_min_momentum_score_bullish_parsing(monkeypatch):
    # Simulate command-line arguments
    test_args = [
        '--chain', 'ethereum',
        '--token', 'WETH',
        '--min-momentum-score-bullish', '5.5',
        '--min-momentum-score-bearish', '2.0',
        '--scanner-enabled' # Required for the scanner to be enabled
    ]
    monkeypatch.setattr('argparse.ArgumentParser.parse_args', lambda self: argparse.Namespace(
        chain=['ethereum'],
        token=['WETH'],
        dex_fee=0.3,
        slippage=0.5,
        min_bullish_profit=0.0,
        min_bearish_discrepancy=1.0,
        min_momentum_score_bullish=5.5,
        min_momentum_score_bearish=2.0,
        trade_volume=500.0,
        min_liquidity=1000.0,
        min_volume=1000.0,
        min_txns_h1=1,
        interval=60,
        telegram_enabled=False,
        twitter_enabled=False,
        alert_cooldown=3600,
        multi_leg=False,
        max_cycle_length=3,
        max_depth=2,
        scanner_enabled=True,
        disable_ai_analysis=False,
    ))
    config = load_config()
    assert config.min_momentum_score_bullish == 5.5
    assert config.min_momentum_score_bearish == 2.0

def test_min_momentum_score_default_values(monkeypatch):
    # Simulate command-line arguments without specifying momentum scores
    test_args = [
        '--chain', 'ethereum',
        '--token', 'WETH',
        '--scanner-enabled'
    ]
    monkeypatch.setattr('argparse.ArgumentParser.parse_args', lambda self: argparse.Namespace(
        chain=['ethereum'],
        token=['WETH'],
        dex_fee=0.3,
        slippage=0.5,
        min_bullish_profit=0.0,
        min_bearish_discrepancy=1.0,
        min_momentum_score_bullish=0.0, # Default
        min_momentum_score_bearish=0.0, # Default
        trade_volume=500.0,
        min_liquidity=1000.0,
        min_volume=1000.0,
        min_txns_h1=1,
        interval=60,
        telegram_enabled=False,
        twitter_enabled=False,
        alert_cooldown=3600,
        multi_leg=False,
        max_cycle_length=3,
        max_depth=2,
        scanner_enabled=True,
        disable_ai_analysis=False,
    ))
    config = load_config()
    assert config.min_momentum_score_bullish == 0.0
    assert config.min_momentum_score_bearish == 0.0
