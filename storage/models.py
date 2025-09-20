"""Dataclasses representing stored arbitrage records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class ScanCycleRecord:
    id: int
    started_at: datetime
    finished_at: Optional[datetime]
    chains: list[str]
    tokens: list[str]
    opportunities_found: int


@dataclass(slots=True)
class OpportunityAlertRecord:
    id: int
    scan_cycle_id: Optional[int]
    chain: str
    token: str
    direction: str
    net_profit_usd: float
    gross_profit_usd: float
    momentum_score: float
    alert_sent_at: datetime
    opportunity_key: str


@dataclass(slots=True)
class MomentumSnapshotRecord:
    id: int
    alert_id: int
    volume_divergence: Optional[float]
    persistence_count: Optional[int]
    rsi_value: Optional[float]
    dominant_dex_has_lower_price: bool
    raw_payload: Optional[dict]
