"""Data models for the Pipeline Risk Snapshot feature."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class WoWDelta(BaseModel):
    """Week-over-week change for a single metric."""
    value: float | int | None = None   # absolute change (None = no prior snapshot)
    pct: float | None = None           # percentage change (None if prior was 0 or absent)


class SnapshotMetrics(BaseModel):
    """Aggregate pipeline health metrics for the snapshot header block."""
    pipeline_value: float
    active_deal_count: int
    deals_at_risk_count: int
    risks_resolved_count: int          # total levers NOT at WEAK across diagnosed sessions
    pipeline_value_strengthened: float
    deals_strengthened_count: int      # sessions with ≥1 lever > WEAK

    # WoW deltas — all None on first generation
    pipeline_value_delta: WoWDelta = WoWDelta()
    active_deal_count_delta: WoWDelta = WoWDelta()
    deals_at_risk_delta: WoWDelta = WoWDelta()
    risks_resolved_delta: WoWDelta = WoWDelta()
    pipeline_value_strengthened_delta: WoWDelta = WoWDelta()


class DealRiskEntry(BaseModel):
    """One row in the Active Structural Risk deal table."""
    opportunity_id: str
    user_id: str
    deal_value: float | None
    zone_display: str | None           # e.g. "Zone 3 — Validation"
    core_risks: list[str]              # lever display names at WEAK
    active_strategy: str | None        # strategy path display_name
    next_move: str | None              # ux_text of last selected action


class ForecastThreats(BaseModel):
    """Aggregate % breakdowns for the Forecast Threats section."""
    # {lever_display_name: pct_of_deals_where_weak}
    top_failure_modes: dict[str, float]
    # {strategy_display_name: pct_of_diagnosed_deals}
    active_strategy_interventions: dict[str, float]
    # {pattern_display_name: pct_of_diagnosed_deals}
    dominant_risk_patterns: dict[str, float]


class PipelineSnapshot(BaseModel):
    """Full snapshot payload — rendered to Markdown by renderer.py."""
    snapshot_id: str
    week_start: str    # ISO date — Sunday
    week_end: str      # ISO date — Saturday
    generated_at: str
    metrics: SnapshotMetrics
    at_risk_deals: list[DealRiskEntry]
    forecast_threats: ForecastThreats


class PipelineSnapshotDocument(BaseModel):
    """Persisted record in Cosmos snapshots container for WoW delta computation."""
    id: str                            # == snapshot_id (Cosmos requires 'id')
    snapshot_id: str
    week_start: str
    week_end: str
    generated_at: str
    # Raw metric values only — enough to compute next week's WoW deltas
    pipeline_value: float
    active_deal_count: int
    deals_at_risk_count: int
    risks_resolved_count: int
    pipeline_value_strengthened: float
    deals_strengthened_count: int
