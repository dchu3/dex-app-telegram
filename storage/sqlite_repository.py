"""SQLite-backed persistence layer for arbitrage scans and alerts."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from storage.models import MomentumSnapshotRecord, OpportunityAlertRecord, ScanCycleRecord

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _serialize_list(values: Iterable[str]) -> str:
    return ",".join(sorted(set(values)))


class SQLiteRepository:
    """Provides async-friendly helpers for persisting arbitrage activity."""

    def __init__(self, db_path: Path | str = Path("data/momentum_history.db")) -> None:
        self.db_path = Path(db_path)
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._configure()
        self._create_schema()

    def _configure(self) -> None:
        with self._lock:
            cursor = self._connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
            except sqlite3.DatabaseError:
                pass
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    def _create_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS scan_cycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                chains TEXT NOT NULL,
                tokens TEXT NOT NULL,
                opportunities_found INTEGER NOT NULL DEFAULT 0
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS opportunity_alert (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_cycle_id INTEGER,
                chain TEXT NOT NULL,
                token TEXT NOT NULL,
                direction TEXT NOT NULL,
                net_profit_usd REAL NOT NULL,
                gross_profit_usd REAL NOT NULL,
                momentum_score REAL NOT NULL,
                alert_sent_at TEXT NOT NULL,
                opportunity_key TEXT NOT NULL,
                FOREIGN KEY (scan_cycle_id) REFERENCES scan_cycle(id) ON DELETE SET NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS momentum_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                volume_divergence REAL,
                persistence_count INTEGER,
                rsi_value REAL,
                dominant_dex_has_lower_price INTEGER NOT NULL,
                raw_payload TEXT,
                FOREIGN KEY (alert_id) REFERENCES opportunity_alert(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_opportunity_alert_token_time
                ON opportunity_alert(token, alert_sent_at);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_opportunity_alert_key
                ON opportunity_alert(opportunity_key);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_momentum_snapshot_alert
                ON momentum_snapshot(alert_id);
            """,
        ]

        with self._lock:
            cursor = self._connection.cursor()
            for statement in statements:
                cursor.execute(statement)
            self._connection.commit()
            cursor.close()

    async def record_scan_cycle_start(self, chains: Iterable[str], tokens: Iterable[str]) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._record_scan_cycle_start_sync,
            list(chains),
            list(tokens),
        )

    def _record_scan_cycle_start_sync(self, chains: list[str], tokens: list[str]) -> int:
        serialized_chains = _serialize_list(chains)
        serialized_tokens = _serialize_list(tokens)
        started_at = datetime.now(timezone.utc).strftime(ISO_FORMAT)
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                INSERT INTO scan_cycle (started_at, chains, tokens)
                VALUES (?, ?, ?)
                """,
                (started_at, serialized_chains, serialized_tokens),
            )
            self._connection.commit()
            cycle_id = cursor.lastrowid
            cursor.close()
        return cycle_id

    async def record_scan_cycle_finish(self, scan_cycle_id: int, opportunities_found: int) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self._record_scan_cycle_finish_sync,
            scan_cycle_id,
            opportunities_found,
        )

    def _record_scan_cycle_finish_sync(self, scan_cycle_id: int, opportunities_found: int) -> None:
        finished_at = datetime.now(timezone.utc).strftime(ISO_FORMAT)
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                UPDATE scan_cycle
                SET finished_at = ?, opportunities_found = ?
                WHERE id = ?
                """,
                (finished_at, opportunities_found, scan_cycle_id),
            )
            self._connection.commit()
            cursor.close()

    async def record_opportunity_alert(
        self,
        *,
        scan_cycle_id: Optional[int],
        chain: str,
        token: str,
        direction: str,
        net_profit_usd: float,
        gross_profit_usd: float,
        momentum_score: float,
        opportunity_key: str,
        alert_sent_at: datetime,
        volume_divergence: Optional[float],
        persistence_count: Optional[int],
        rsi_value: Optional[float],
        dominant_dex_has_lower_price: bool,
        raw_payload: Optional[dict] = None,
    ) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._record_opportunity_alert_sync,
            scan_cycle_id,
            chain,
            token,
            direction,
            net_profit_usd,
            gross_profit_usd,
            momentum_score,
            opportunity_key,
            alert_sent_at,
            volume_divergence,
            persistence_count,
            rsi_value,
            dominant_dex_has_lower_price,
            raw_payload,
        )

    def _record_opportunity_alert_sync(
        self,
        scan_cycle_id: Optional[int],
        chain: str,
        token: str,
        direction: str,
        net_profit_usd: float,
        gross_profit_usd: float,
        momentum_score: float,
        opportunity_key: str,
        alert_sent_at: datetime,
        volume_divergence: Optional[float],
        persistence_count: Optional[int],
        rsi_value: Optional[float],
        dominant_dex_has_lower_price: bool,
        raw_payload: Optional[dict],
    ) -> int:
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                INSERT INTO opportunity_alert (
                    scan_cycle_id,
                    chain,
                    token,
                    direction,
                    net_profit_usd,
                    gross_profit_usd,
                    momentum_score,
                    alert_sent_at,
                    opportunity_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_cycle_id,
                    chain,
                    token,
                    direction,
                    net_profit_usd,
                    gross_profit_usd,
                    momentum_score,
                    alert_sent_at.strftime(ISO_FORMAT),
                    opportunity_key,
                ),
            )
            alert_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO momentum_snapshot (
                    alert_id,
                    volume_divergence,
                    persistence_count,
                    rsi_value,
                    dominant_dex_has_lower_price,
                    raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    volume_divergence,
                    persistence_count,
                    rsi_value,
                    1 if dominant_dex_has_lower_price else 0,
                    json.dumps(raw_payload) if raw_payload is not None else None,
                ),
            )
            self._connection.commit()
            cursor.close()
        return alert_id

    async def fetch_recent_alerts(self, limit: int = 50) -> list[OpportunityAlertRecord]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_recent_alerts_sync, limit)

    def _fetch_recent_alerts_sync(self, limit: int) -> list[OpportunityAlertRecord]:
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                SELECT * FROM opportunity_alert
                ORDER BY alert_sent_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            cursor.close()
        records: list[OpportunityAlertRecord] = []
        for row in rows:
            records.append(
                OpportunityAlertRecord(
                    id=row["id"],
                    scan_cycle_id=row["scan_cycle_id"],
                    chain=row["chain"],
                    token=row["token"],
                    direction=row["direction"],
                    net_profit_usd=row["net_profit_usd"],
                    gross_profit_usd=row["gross_profit_usd"],
                    momentum_score=row["momentum_score"],
                    alert_sent_at=datetime.strptime(row["alert_sent_at"], ISO_FORMAT),
                    opportunity_key=row["opportunity_key"],
                )
            )
        return records

    async def fetch_momentum_snapshot(self, alert_id: int) -> Optional[MomentumSnapshotRecord]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_momentum_snapshot_sync, alert_id)

    def _fetch_momentum_snapshot_sync(self, alert_id: int) -> Optional[MomentumSnapshotRecord]:
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                SELECT * FROM momentum_snapshot
                WHERE alert_id = ?
                """,
                (alert_id,)
            )
            row = cursor.fetchone()
            cursor.close()
        if row is None:
            return None
        raw_payload = row["raw_payload"]
        return MomentumSnapshotRecord(
            id=row["id"],
            alert_id=row["alert_id"],
            volume_divergence=row["volume_divergence"],
            persistence_count=row["persistence_count"],
            rsi_value=row["rsi_value"],
            dominant_dex_has_lower_price=bool(row["dominant_dex_has_lower_price"]),
            raw_payload=json.loads(raw_payload) if raw_payload else None,
        )

    async def fetch_momentum_records(
        self,
        *,
        limit: int,
        token: Optional[str],
        direction: Optional[str],
    ) -> list[dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._fetch_momentum_records_sync,
            limit,
            token.upper() if token else None,
            direction,
        )

    def _fetch_momentum_records_sync(
        self,
        limit: int,
        token: Optional[str],
        direction: Optional[str],
    ) -> list[dict]:
        query = """
            SELECT
                oa.alert_sent_at,
                oa.chain,
                oa.token,
                oa.direction,
                oa.net_profit_usd,
                oa.gross_profit_usd,
                oa.momentum_score,
                oa.opportunity_key,
                ms.volume_divergence,
                ms.persistence_count,
                ms.rsi_value,
                ms.dominant_dex_has_lower_price,
                ms.raw_payload
            FROM opportunity_alert oa
            LEFT JOIN momentum_snapshot ms ON ms.alert_id = oa.id
            WHERE (? IS NULL OR oa.token = ?)
              AND (? IS NULL OR oa.direction = ?)
            ORDER BY oa.alert_sent_at DESC
            LIMIT ?
        """
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                query,
                (token, token, direction, direction, limit),
            )
            rows = cursor.fetchall()
            cursor.close()

        records: list[dict] = []
        for row in rows:
            raw_payload = json.loads(row["raw_payload"]) if row["raw_payload"] else {}
            momentum = raw_payload.get("momentum", {})
            trend = raw_payload.get("trend") or {}
            dominant_volume_ratio = raw_payload.get("dominant_volume_ratio")
            if dominant_volume_ratio is None:
                dominant_volume_ratio = momentum.get("dominant_volume_ratio")

            flow_side = raw_payload.get("dominant_flow_side")
            if flow_side is None:
                flow_hint = raw_payload.get("dominant_dex_has_lower_price")
                if flow_hint is not None:
                    flow_side = "buy" if flow_hint else "sell"
                elif row["direction"]:
                    flow_side = "buy" if row["direction"] == "BULLISH" else "sell"

            record = {
                "alert_time": datetime.strptime(row["alert_sent_at"], ISO_FORMAT),
                "chain": row["chain"],
                "token": row["token"],
                "direction": row["direction"],
                "net_profit_usd": row["net_profit_usd"],
                "gross_profit_usd": row["gross_profit_usd"],
                "momentum_score": row["momentum_score"],
                "opportunity_key": row["opportunity_key"],
                "volume_divergence": row["volume_divergence"],
                "persistence_count": row["persistence_count"],
                "rsi_value": row["rsi_value"],
                "dominant_dex_has_lower_price": bool(row["dominant_dex_has_lower_price"]) if row["dominant_dex_has_lower_price"] is not None else None,
                "spread_pct": raw_payload.get("spread_pct"),
                "price_impact_pct": raw_payload.get("price_impact_pct"),
                "is_early_momentum": raw_payload.get("is_early_momentum", False),
                "short_term_volume_ratio": momentum.get("short_term_volume_ratio"),
                "short_term_txns_total": momentum.get("short_term_txns_total"),
                "momentum_volume_divergence": momentum.get("volume_divergence"),
                "persistence_count_window": momentum.get("persistence_count"),
                "dominant_volume_ratio": dominant_volume_ratio,
                "flow_side": flow_side,
                "effective_volume_usd": raw_payload.get("effective_volume_usd"),
                "buy_dex": raw_payload.get("buy_dex"),
                "sell_dex": raw_payload.get("sell_dex"),
                "trend_buy_change_h1": trend.get("buy_price_change_h1"),
                "trend_sell_change_h1": trend.get("sell_price_change_h1"),
                "raw_payload": raw_payload,
            }
            records.append(record)
        return records

    async def close(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            self._connection.commit()
            self._connection.close()


__all__ = ["SQLiteRepository", "ScanCycleRecord", "OpportunityAlertRecord", "MomentumSnapshotRecord"]
