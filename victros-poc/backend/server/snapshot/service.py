"""Snapshot generation service.

generate_snapshot(repo, schema_store, snapshot_store, *, week_start, week_end)
  -> PipelineSnapshot

Algorithm:
  1. list_all_sessions() from repo
  2. Filter to diagnosed states
  3. Count lever improvements from interaction_history within the reporting window
  4. Compute current-state metrics (pipeline value, deal counts)
  5. Load prior PipelineSnapshotDocument for WoW deltas
  6. Build at-risk deal table (risk prioritization per addendum spec)
  7. Build forecast threats (top-N capped per addendum spec)
  8. Upsert PipelineSnapshotDocument for this week
  9. Return PipelineSnapshot

Week boundaries: Sunday 00:00 UTC → Saturday 23:59 UTC.
The scheduler passes explicit week_start / week_end; API calls may omit them
to get the current week automatically.
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from server.db.base import SessionRepository
from server.models import SessionState
from server.schema_store import SchemaStore
from server.snapshot.models import (
    DealRiskEntry,
    ForecastThreats,
    PipelineSnapshot,
    PipelineSnapshotDocument,
    SnapshotMetrics,
    WoWDelta,
)

if TYPE_CHECKING:
    from server.snapshot.store import FileSnapshotStore, CosmosSnapshotStore

# States considered "diagnosed" — sessions that have completed the engine run
_DIAGNOSED_STATES = {
    "PRESENTING_DIAGNOSIS",
    "ACTION_SELECTION",
    "DUAL_PATTERN_TRADEOFF",
    "MONITORING",
    "RE_EVALUATING",
}

_WEAK = "WEAK"

# Lever state advancement order — higher index = more advanced
_LEVER_STATE_ORDER = {"WEAK": 0, "CONNECTED": 1, "COMMITTED": 2, "EXECUTING": 3}

# The four "core" levers prioritized in the risk display, in order.
# Primary = first WEAK lever found in this list; Secondary = all remaining WEAK levers.
_CORE_LEVER_PRIORITY = [
    "case_for_change_strength",
    "champion_strength",
    "economic_buyer_commitment",
    "decision_process_alignment",
]

# Top-N caps per addendum spec
_TOP_FAILURE_MODES_CAP = 4
_TOP_STRATEGIES_CAP = 6
_TOP_PATTERNS_CAP = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _current_week_start() -> date:
    """Return the most recent Sunday (UTC) as a date."""
    today = datetime.now(timezone.utc).date()
    # weekday(): Monday=0 … Sunday=6
    days_since_sunday = (today.weekday() + 1) % 7
    return today - timedelta(days=days_since_sunday)


def _fmt(d: date) -> str:
    return d.isoformat()


def _wow(current: float | int, previous: float | int | None) -> WoWDelta:
    if previous is None:
        return WoWDelta()
    diff = current - previous
    pct = (diff / previous * 100) if previous else None
    return WoWDelta(value=round(diff, 2), pct=round(pct, 1) if pct is not None else None)


def generate_snapshot(
    repo: SessionRepository,
    schema_store: SchemaStore,
    snapshot_store: "FileSnapshotStore | CosmosSnapshotStore",
    *,
    week_start: date | None = None,
    week_end: date | None = None,
) -> PipelineSnapshot:
    """Generate and persist a Pipeline Risk Snapshot.

    week_start / week_end are optional. When omitted the current calendar week
    (Sunday–Saturday UTC) is used. The Azure scheduler passes them explicitly.
    """
    if week_start is None:
        week_start = _current_week_start()
    if week_end is None:
        week_end = week_start + timedelta(days=6)
    now = datetime.now(timezone.utc).isoformat()

    # 1. Load and filter sessions
    all_sessions = repo.list_all_sessions()
    diagnosed = [s for s in all_sessions if s.state in _DIAGNOSED_STATES]

    # 2. Current-state metrics
    pipeline_value = sum(
        (s.deal_snapshot.amount or 0) for s in diagnosed if s.deal_snapshot
    )
    active_deal_count = len(diagnosed)

    deals_at_risk = [
        s for s in diagnosed
        if any(v == _WEAK for v in s.lever_states.values())
    ]
    deals_at_risk_count = len(deals_at_risk)

    strengthened = [
        s for s in diagnosed
        if any(v != _WEAK for v in s.lever_states.values())
    ]
    pipeline_value_strengthened = sum(
        (s.deal_snapshot.amount or 0) for s in strengthened if s.deal_snapshot
    )
    deals_strengthened_count = len(strengthened)

    # 3. Structural Risks Resolved — count lever improvements from history
    #    within the reporting window (cumulative when no start bound given).
    risks_resolved_count = _count_lever_improvements(
        diagnosed, start_date=week_start, end_date=week_end
    )

    # 4. Load prior snapshot for WoW deltas
    prior_week_start = _fmt(week_start - timedelta(days=7))
    prior = snapshot_store.get_by_week_start(prior_week_start)

    metrics = SnapshotMetrics(
        pipeline_value=pipeline_value,
        active_deal_count=active_deal_count,
        deals_at_risk_count=deals_at_risk_count,
        risks_resolved_count=risks_resolved_count,
        pipeline_value_strengthened=pipeline_value_strengthened,
        deals_strengthened_count=deals_strengthened_count,
        pipeline_value_delta=_wow(pipeline_value, prior.pipeline_value if prior else None),
        active_deal_count_delta=_wow(active_deal_count, prior.active_deal_count if prior else None),
        deals_at_risk_delta=_wow(deals_at_risk_count, prior.deals_at_risk_count if prior else None),
        risks_resolved_delta=_wow(risks_resolved_count, prior.risks_resolved_count if prior else None),
        pipeline_value_strengthened_delta=_wow(
            pipeline_value_strengthened,
            prior.pipeline_value_strengthened if prior else None,
        ),
    )

    # 5. Build at-risk deal table (sorted by deal value desc)
    at_risk_deals = [_build_deal_entry(s, schema_store) for s in deals_at_risk]
    at_risk_deals.sort(key=lambda d: d.deal_value or 0, reverse=True)

    # 6. Forecast threats
    forecast_threats = _build_forecast_threats(diagnosed, schema_store)

    # 7. Compose snapshot
    snapshot_id = str(uuid.uuid4())
    snapshot = PipelineSnapshot(
        snapshot_id=snapshot_id,
        week_start=_fmt(week_start),
        week_end=_fmt(week_end),
        generated_at=now,
        metrics=metrics,
        at_risk_deals=at_risk_deals,
        forecast_threats=forecast_threats,
    )

    # 8. Persist for next week's WoW calculation
    doc = PipelineSnapshotDocument(
        id=snapshot_id,
        snapshot_id=snapshot_id,
        week_start=_fmt(week_start),
        week_end=_fmt(week_end),
        generated_at=now,
        pipeline_value=pipeline_value,
        active_deal_count=active_deal_count,
        deals_at_risk_count=deals_at_risk_count,
        risks_resolved_count=risks_resolved_count,
        pipeline_value_strengthened=pipeline_value_strengthened,
        deals_strengthened_count=deals_strengthened_count,
    )
    snapshot_store.upsert(doc)

    return snapshot


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_lever_improvements(
    sessions: list[SessionState],
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Count lever state improvements recorded in interaction_history.

    Each 'lever_state_change' history entry contains a list of changes where
    the lever advanced (WEAK→CONNECTED, CONNECTED→COMMITTED, etc.). Those
    entries were written by the confirm endpoint at the moment the Decision
    Engine result was applied.

    start_date / end_date filter by the entry's timestamp date (ISO prefix).
    Passing None for either bound means open-ended (cumulative from/to all time).
    """
    count = 0
    start_str = start_date.isoformat() if start_date else None
    end_str = end_date.isoformat() if end_date else None

    for session in sessions:
        for entry in session.interaction_history:
            if entry.get("type") != "lever_state_change":
                continue
            ts = entry.get("timestamp", "")
            ts_date = ts[:10] if ts else ""
            if start_str and ts_date and ts_date < start_str:
                continue
            if end_str and ts_date and ts_date > end_str:
                continue
            count += len(entry.get("changes", []))

    return count


def _build_deal_entry(session: SessionState, schema_store: SchemaStore) -> DealRiskEntry:
    # Zone display: "Zone 3 — Validation" (single display_name word per spec)
    zone_display: str | None = None
    if session.deal_snapshot and session.deal_snapshot.stage:
        zone = schema_store.get_zone_for_stage(session.deal_snapshot.stage)
        if zone:
            num = zone.key.replace("zone", "")
            zone_display = f"Zone {num} — {zone.display_name}"

    # Core Structural Risk — two-tier per addendum:
    #   Primary (bolded) = highest-priority WEAK lever among the 4 core levers
    #   Secondary        = all remaining WEAK levers
    weak_keys = {k for k, v in session.lever_states.items() if v == _WEAK}

    primary_lever_key: str | None = None
    for key in _CORE_LEVER_PRIORITY:
        if key in weak_keys:
            primary_lever_key = key
            break

    def _lever_name(key: str) -> str:
        lever = schema_store.get_lever(key)
        return lever.name if lever else key.replace("_", " ").title()

    primary_risk: str | None = _lever_name(primary_lever_key) if primary_lever_key else None

    # Secondary = all WEAK levers except the chosen primary
    secondary_keys = weak_keys - ({primary_lever_key} if primary_lever_key else set())
    # Preserve a stable order: core priority levers first, then the remaining 3
    ordered_secondary: list[str] = []
    for key in _CORE_LEVER_PRIORITY:
        if key in secondary_keys:
            ordered_secondary.append(key)
    for key in session.lever_states:
        if key in secondary_keys and key not in ordered_secondary:
            ordered_secondary.append(key)
    secondary_risks = [_lever_name(k) for k in ordered_secondary]

    # Flat list for DealRiskEntry: primary first (renderer bolds it), then secondary
    core_risks = ([primary_risk] if primary_risk else []) + secondary_risks

    # Active strategy display name
    active_strategy: str | None = None
    if session.selected_strategy_path:
        sp = schema_store.get_strategy_path(session.selected_strategy_path)
        active_strategy = sp.display_name if sp else session.selected_strategy_path

    # Next move: ux_text of the last selected action in history
    next_move: str | None = None
    for entry in reversed(session.interaction_history):
        if entry.get("type") == "action_selected":
            action_key = entry.get("action_key")
            if action_key:
                action = schema_store.get_representative_action(action_key)
                next_move = action.ux_text if action else None
            break

    return DealRiskEntry(
        opportunity_id=session.opportunity_id,
        user_id=session.user_id,
        deal_value=session.deal_snapshot.amount if session.deal_snapshot else None,
        zone_display=zone_display,
        core_risks=core_risks,
        active_strategy=active_strategy,
        next_move=next_move,
    )


def _build_forecast_threats(
    diagnosed: list[SessionState],
    schema_store: SchemaStore,
) -> ForecastThreats:
    total = len(diagnosed)
    if total == 0:
        return ForecastThreats(
            top_failure_modes={},
            active_strategy_interventions={},
            dominant_risk_patterns={},
        )

    # Top Failure Modes: % of deals where each lever is WEAK, capped at 4
    lever_weak_counts: Counter = Counter()
    for s in diagnosed:
        for lever_key, state in s.lever_states.items():
            if state == _WEAK:
                lever = schema_store.get_lever(lever_key)
                name = lever.name if lever else lever_key.replace("_", " ").title()
                lever_weak_counts[name] += 1

    top_failure_modes = {
        name: round(count / total * 100, 1)
        for name, count in lever_weak_counts.most_common(_TOP_FAILURE_MODES_CAP)
        if count > 0
    }

    # Active Strategy Interventions: % distribution of strategy paths, capped at 6
    strategy_counts: Counter = Counter()
    for s in diagnosed:
        if s.selected_strategy_path:
            sp = schema_store.get_strategy_path(s.selected_strategy_path)
            name = sp.display_name if sp else s.selected_strategy_path
            strategy_counts[name] += 1

    active_strategy_interventions = {
        name: round(count / total * 100, 1)
        for name, count in strategy_counts.most_common(_TOP_STRATEGIES_CAP)
    }

    # Dominant Risk Patterns: % of deals per primary pattern, capped at 3
    pattern_counts: Counter = Counter()
    for s in diagnosed:
        if s.active_patterns.primary:
            p = schema_store.get_pattern(s.active_patterns.primary)
            name = p.name if p else s.active_patterns.primary.replace("_", " ").title()
            pattern_counts[name] += 1

    dominant_risk_patterns = {
        name: round(count / total * 100, 1)
        for name, count in pattern_counts.most_common(_TOP_PATTERNS_CAP)
    }

    return ForecastThreats(
        top_failure_modes=top_failure_modes,
        active_strategy_interventions=active_strategy_interventions,
        dominant_risk_patterns=dominant_risk_patterns,
    )
