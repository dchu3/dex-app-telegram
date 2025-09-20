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
