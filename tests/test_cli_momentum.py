import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

import main


class FakeRepository:
    def __init__(self):
        pass

    async def fetch_momentum_records(self, *, limit, token, direction):
        return [
            {
                "alert_time": datetime(2024, 1, 1, 12, 0, 0),
                "token": "BRETT",
                "chain": "base",
                "direction": "BULLISH",
                "momentum_score": 6.2,
                "spread_pct": 1.5,
                "net_profit_usd": 8.4,
                "short_term_volume_ratio": 0.18,
                "short_term_txns_total": 5,
                "is_early_momentum": True,
            }
        ]

    async def close(self):
        pass


@pytest.mark.usefixtures("reset_sys_argv")
def test_show_momentum_cli_outputs_table(monkeypatch, capsys):
    monkeypatch.setattr(main, "SQLiteRepository", lambda: FakeRepository())
    monkeypatch.setenv("ETHERSCAN_API_KEY", "dummy")

    sys.argv = ["prog", "--show-momentum"]
    main.main()

    output = capsys.readouterr().out
    assert "Showing up to 10 momentum records" in output
    assert "BRETT" in output
    assert "BULLISH" in output
    assert "1.5" in output


@pytest.fixture
def reset_sys_argv():
    original = sys.argv.copy()
    yield
    sys.argv = original
