from datetime import datetime, timezone

import pytest

from storage import SQLiteRepository


@pytest.mark.asyncio
async def test_persist_scan_cycle_and_momentum_snapshot(tmp_path):
    db_path = tmp_path / "test.db"
    repository = SQLiteRepository(db_path=db_path)

    scan_id = await repository.record_scan_cycle_start(["base"], ["BRETT", "AERO"])
    assert isinstance(scan_id, int)

    dispatched_at = datetime.now(timezone.utc)
    alert_id = await repository.record_opportunity_alert(
        scan_cycle_id=scan_id,
        chain="base",
        token="BRETT",
        direction="BULLISH",
        net_profit_usd=12.34,
        gross_profit_usd=15.0,
        momentum_score=6.5,
        opportunity_key="base-BRETT-foo-bar",
        alert_sent_at=dispatched_at,
        volume_divergence=2.5,
        persistence_count=3,
        rsi_value=45.0,
        dominant_dex_has_lower_price=True,
        raw_payload={"mock": "payload"},
    )

    await repository.record_scan_cycle_finish(scan_id, 1)

    alerts = await repository.fetch_recent_alerts()
    assert len(alerts) == 1
    assert alerts[0].id == alert_id
    assert alerts[0].scan_cycle_id == scan_id
    assert alerts[0].token == "BRETT"

    snapshot = await repository.fetch_momentum_snapshot(alert_id)
    assert snapshot is not None
    assert snapshot.alert_id == alert_id
    assert snapshot.dominant_dex_has_lower_price is True
    assert snapshot.raw_payload == {"mock": "payload"}

    await repository.close()


@pytest.mark.asyncio
async def test_fetch_momentum_records_filters(tmp_path):
    db_path = tmp_path / "momentum.db"
    repository = SQLiteRepository(db_path=db_path)

    scan_id = await repository.record_scan_cycle_start(["base"], ["BRETT"])
    dispatched_at = datetime.now(timezone.utc)

    await repository.record_opportunity_alert(
        scan_cycle_id=scan_id,
        chain="base",
        token="BRETT",
        direction="BULLISH",
        net_profit_usd=9.99,
        gross_profit_usd=12.0,
        momentum_score=6.5,
        opportunity_key="base-BRETT-foo-bar",
        alert_sent_at=dispatched_at,
        volume_divergence=2.5,
        persistence_count=4,
        rsi_value=55.0,
        dominant_dex_has_lower_price=True,
        raw_payload={
            "spread_pct": 1.7,
            "price_impact_pct": 0.8,
            "is_early_momentum": True,
            "effective_volume_usd": 750.0,
            "dominant_volume_ratio": 2.2,
            "dominant_flow_side": "sell",
            "trend": {
                "buy_price_change_h1": 1.1,
                "sell_price_change_h1": 1.6,
            },
            "momentum": {
                "short_term_volume_ratio": 0.22,
                "short_term_txns_total": 6,
                "volume_divergence": 2.4,
                "persistence_count": 4,
                "dominant_volume_ratio": 2.2,
            },
        },
    )

    records = await repository.fetch_momentum_records(limit=5, token="brett", direction="BULLISH")
    assert len(records) == 1
    rec = records[0]
    assert rec["token"] == "BRETT"
    assert rec["direction"] == "BULLISH"
    assert rec["spread_pct"] == 1.7
    assert rec["short_term_txns_total"] == 6
    assert rec["is_early_momentum"] is True
    assert rec["dominant_volume_ratio"] == 2.2
    assert rec["flow_side"] == "sell"
    assert rec["effective_volume_usd"] == 750.0
    assert rec["trend_buy_change_h1"] == 1.1
    assert rec["trend_sell_change_h1"] == 1.6

    await repository.close()
