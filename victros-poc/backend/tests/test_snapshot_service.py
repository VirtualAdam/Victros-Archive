"""Unit tests for snapshot service and renderer (SS-01 → SS-28).

All tests use in-memory / tmp-path fakes — no Cosmos, no disk I/O beyond
what FileSnapshotStore needs.
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def schema_store():
    from server.schema_store import SchemaStore
    return SchemaStore(SCHEMA_DIR)


@pytest.fixture
def snap_store(tmp_path):
    from server.snapshot.store import FileSnapshotStore
    return FileSnapshotStore(tmp_path / "snapshots")


def _make_session(
    state="MONITORING",
    lever_states=None,
    amount=None,
    stage="zone2",
    strategy_path="building_champions",
    primary_pattern="no_named_or_active_champion",
    action_key=None,
    user_id="user_001",
    opportunity_id="OppA",
    extra_history=None,
):
    from server.models import (
        ActivePatterns, DealSnapshot, IntakeReadiness, SessionState,
    )
    from server.session_manager import DEFAULT_LEVER_STATES

    levers = dict(DEFAULT_LEVER_STATES)
    if lever_states:
        levers.update(lever_states)

    history = []
    if action_key:
        history.append({"type": "action_selected", "action_key": action_key})
    if extra_history:
        history.extend(extra_history)

    return SessionState(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        opportunity_id=opportunity_id,
        state=state,
        deal_snapshot=DealSnapshot(stage=stage, amount=amount),
        active_signals=[],
        active_patterns=ActivePatterns(primary=primary_pattern, secondary=[]),
        selected_strategy_path=strategy_path,
        lever_states=levers,
        interaction_history=history,
        intake_readiness=IntakeReadiness(),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


class _MockRepo:
    """Minimal SessionRepository stand-in backed by a list."""
    def __init__(self, sessions):
        self._sessions = sessions

    def list_all_sessions(self):
        return list(self._sessions)

    def create_session(self, *a, **k): ...
    def get_session(self, *a, **k): ...
    def update_session(self, *a, **k): ...
    def append_history(self, *a, **k): ...
    def list_sessions(self, *a, **k): ...


def _lever_change_entry(changes, ts=None):
    """Build a lever_state_change interaction history entry."""
    return {
        "type": "lever_state_change",
        "changes": changes,
        "timestamp": ts or datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
class TestSnapshotMetrics:

    # SS-01: empty pipeline produces zero metrics
    def test_ss01_empty_pipeline(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        snap = generate_snapshot(_MockRepo([]), schema_store, snap_store)
        assert snap.metrics.pipeline_value == 0
        assert snap.metrics.active_deal_count == 0
        assert snap.metrics.deals_at_risk_count == 0
        assert snap.metrics.risks_resolved_count == 0

    # SS-02: non-diagnosed sessions are excluded
    def test_ss02_undiagnosed_excluded(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        s = _make_session(state="INTAKE", amount=500_000)
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        assert snap.metrics.active_deal_count == 0

    # SS-03: pipeline_value sums deal amounts for diagnosed sessions
    def test_ss03_pipeline_value(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        sessions = [
            _make_session(amount=1_000_000, opportunity_id="A"),
            _make_session(amount=500_000, opportunity_id="B"),
        ]
        snap = generate_snapshot(_MockRepo(sessions), schema_store, snap_store)
        assert snap.metrics.pipeline_value == 1_500_000

    # SS-04: deals_at_risk counts sessions with ≥1 WEAK lever
    def test_ss04_deals_at_risk(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        all_connected = {k: "CONNECTED" for k in [
            "case_for_change_strength", "champion_strength",
            "economic_buyer_commitment", "buyer_consensus",
            "decision_process_alignment", "differentiation_leverage", "buyer_urgency",
        ]}
        at_risk = _make_session(lever_states={"champion_strength": "WEAK"}, opportunity_id="R")
        healthy = _make_session(lever_states=all_connected, opportunity_id="H")
        snap = generate_snapshot(_MockRepo([at_risk, healthy]), schema_store, snap_store)
        assert snap.metrics.deals_at_risk_count == 1

    # SS-05: risks_resolved_count uses lever_state_change history entries
    def test_ss05_risks_resolved_from_history(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        change_entry = _lever_change_entry([
            {"lever_key": "champion_strength", "from": "WEAK", "to": "CONNECTED"},
            {"lever_key": "economic_buyer_commitment", "from": "CONNECTED", "to": "COMMITTED"},
        ])
        s = _make_session(extra_history=[change_entry])
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        assert snap.metrics.risks_resolved_count == 2

    # SS-05b: sessions with no lever history contribute 0 to risks_resolved
    def test_ss05b_no_history_zero_resolved(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        s = _make_session()  # no lever_state_change entries
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        assert snap.metrics.risks_resolved_count == 0

    # SS-06: WoW deltas are None when no prior snapshot exists
    def test_ss06_wow_none_on_first_run(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        snap = generate_snapshot(_MockRepo([_make_session(amount=100_000)]), schema_store, snap_store)
        assert snap.metrics.pipeline_value_delta.value is None
        assert snap.metrics.active_deal_count_delta.value is None

    # SS-07: WoW deltas computed correctly from prior snapshot
    def test_ss07_wow_delta_computed(self, schema_store, snap_store):
        from server.snapshot.models import PipelineSnapshotDocument
        from server.snapshot.service import generate_snapshot, _current_week_start

        prior_week = (_current_week_start() - timedelta(days=7)).isoformat()
        prior_doc = PipelineSnapshotDocument(
            id="prior", snapshot_id="prior",
            week_start=prior_week, week_end=prior_week,
            generated_at="2026-01-01T00:00:00+00:00",
            pipeline_value=800_000, active_deal_count=3,
            deals_at_risk_count=2, risks_resolved_count=5,
            pipeline_value_strengthened=200_000, deals_strengthened_count=1,
        )
        snap_store.upsert(prior_doc)
        snap = generate_snapshot(_MockRepo([_make_session(amount=1_000_000)]), schema_store, snap_store)
        assert snap.metrics.pipeline_value_delta.value == 200_000
        assert snap.metrics.active_deal_count_delta.value == -2

    # SS-08: explicit week_start/week_end parameters honoured
    def test_ss08_explicit_week_params(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        ws = date(2026, 3, 1)
        we = date(2026, 3, 7)
        snap = generate_snapshot(_MockRepo([]), schema_store, snap_store, week_start=ws, week_end=we)
        assert snap.week_start == "2026-03-01"
        assert snap.week_end == "2026-03-07"

    # SS-09: lever_state_change entries outside the window are excluded
    def test_ss09_window_filtering(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        ws = date(2026, 4, 6)  # Sunday
        we = date(2026, 4, 12)  # Saturday
        in_window = _lever_change_entry(
            [{"lever_key": "champion_strength", "from": "WEAK", "to": "CONNECTED"}],
            ts="2026-04-08T10:00:00+00:00",
        )
        out_of_window = _lever_change_entry(
            [{"lever_key": "economic_buyer_commitment", "from": "WEAK", "to": "CONNECTED"}],
            ts="2026-03-01T10:00:00+00:00",  # before window
        )
        s = _make_session(extra_history=[in_window, out_of_window])
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store, week_start=ws, week_end=we)
        assert snap.metrics.risks_resolved_count == 1  # only the in-window entry


# ---------------------------------------------------------------------------
class TestDealTable:

    # SS-10: at-risk deals appear in deal table
    def test_ss10_at_risk_in_table(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        s = _make_session(opportunity_id="BigDeal", amount=2_000_000)
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        assert "BigDeal" in [d.opportunity_id for d in snap.at_risk_deals]

    # SS-11: healthy deals not in deal table
    def test_ss11_healthy_not_in_table(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        all_committed = {k: "COMMITTED" for k in [
            "case_for_change_strength", "champion_strength",
            "economic_buyer_commitment", "buyer_consensus",
            "decision_process_alignment", "differentiation_leverage", "buyer_urgency",
        ]}
        snap = generate_snapshot(_MockRepo([_make_session(lever_states=all_committed)]), schema_store, snap_store)
        assert snap.at_risk_deals == []

    # SS-12: deal table sorted by deal value descending
    def test_ss12_deal_table_sorted(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        sessions = [
            _make_session(amount=100_000, opportunity_id="Small"),
            _make_session(amount=2_000_000, opportunity_id="Large"),
            _make_session(amount=500_000, opportunity_id="Mid"),
        ]
        snap = generate_snapshot(_MockRepo(sessions), schema_store, snap_store)
        values = [d.deal_value for d in snap.at_risk_deals]
        assert values == sorted(values, reverse=True)

    # SS-13: zone_display populated from deal_snapshot.stage
    def test_ss13_zone_display(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        s = _make_session(stage="zone3")
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        assert snap.at_risk_deals[0].zone_display is not None
        assert "3" in snap.at_risk_deals[0].zone_display

    # SS-14: Core Structural Risk — primary is the highest-priority WEAK core lever
    def test_ss14_risk_priority_primary(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        # Both case_for_change_strength AND champion_strength are WEAK.
        # case_for_change_strength has higher priority → must be primary (index 0).
        s = _make_session(lever_states={
            "case_for_change_strength": "WEAK",
            "champion_strength": "WEAK",
            "economic_buyer_commitment": "CONNECTED",
            "buyer_consensus": "CONNECTED",
            "decision_process_alignment": "CONNECTED",
            "differentiation_leverage": "CONNECTED",
            "buyer_urgency": "CONNECTED",
        })
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        entry = snap.at_risk_deals[0]
        # primary lever name
        cfcs_lever = schema_store.get_lever("case_for_change_strength")
        assert entry.core_risks[0] == cfcs_lever.name

    # SS-15: Core Structural Risk — non-core WEAK levers appear as secondary
    def test_ss15_risk_secondary_non_core(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        # Only buyer_urgency is WEAK (not in the 4 core levers).
        # There should be no primary, and buyer_urgency should appear as secondary.
        all_connected = {k: "CONNECTED" for k in [
            "case_for_change_strength", "champion_strength",
            "economic_buyer_commitment", "decision_process_alignment",
            "buyer_consensus", "differentiation_leverage",
        ]}
        all_connected["buyer_urgency"] = "WEAK"
        s = _make_session(lever_states=all_connected)
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        entry = snap.at_risk_deals[0]
        # No core lever is WEAK so core_risks[0] should be buyer_urgency
        urgency_lever = schema_store.get_lever("buyer_urgency")
        assert urgency_lever.name in entry.core_risks

    # SS-16: next_move uses ux_text of last selected action
    def test_ss16_next_move_from_action(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        first_action = schema_store.representative_actions[0]
        s = _make_session(action_key=first_action.action_key)
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        assert snap.at_risk_deals[0].next_move == first_action.ux_text

    # SS-17: next_move is None when no action selected
    def test_ss17_next_move_none(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        snap = generate_snapshot(_MockRepo([_make_session(action_key=None)]), schema_store, snap_store)
        assert snap.at_risk_deals[0].next_move is None


# ---------------------------------------------------------------------------
class TestForecastThreats:

    # SS-18: top_failure_modes lists levers at WEAK with correct percentage
    def test_ss18_failure_modes_pct(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        sessions = [_make_session(opportunity_id="A"), _make_session(opportunity_id="B")]
        snap = generate_snapshot(_MockRepo(sessions), schema_store, snap_store)
        lever = schema_store.get_lever("champion_strength")
        assert lever.name in snap.forecast_threats.top_failure_modes
        assert snap.forecast_threats.top_failure_modes[lever.name] == 100.0

    # SS-19: top_failure_modes capped at 4 entries
    def test_ss19_failure_modes_cap(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        snap = generate_snapshot(_MockRepo([_make_session()]), schema_store, snap_store)
        assert len(snap.forecast_threats.top_failure_modes) <= 4

    # SS-20: active_strategy_interventions reflects strategy path distribution
    def test_ss20_strategy_interventions(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        sp_keys = [sp.key for sp in schema_store.strategy_paths[:2]]
        sessions = [
            _make_session(strategy_path=sp_keys[0], opportunity_id="A"),
            _make_session(strategy_path=sp_keys[0], opportunity_id="B"),
            _make_session(strategy_path=sp_keys[1], opportunity_id="C"),
        ]
        snap = generate_snapshot(_MockRepo(sessions), schema_store, snap_store)
        sp0_name = schema_store.get_strategy_path(sp_keys[0]).display_name
        assert snap.forecast_threats.active_strategy_interventions[sp0_name] == pytest.approx(66.7, rel=0.01)

    # SS-21: active_strategy_interventions capped at 6 entries
    def test_ss21_strategy_interventions_cap(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        sessions = [
            _make_session(strategy_path=sp.key, opportunity_id=sp.key)
            for sp in schema_store.strategy_paths
        ]
        snap = generate_snapshot(_MockRepo(sessions), schema_store, snap_store)
        assert len(snap.forecast_threats.active_strategy_interventions) <= 6

    # SS-22: dominant_risk_patterns capped at 3 entries
    def test_ss22_pattern_cap(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        sessions = [
            _make_session(primary_pattern=p.key, opportunity_id=p.key)
            for p in schema_store.patterns[:10]
        ]
        snap = generate_snapshot(_MockRepo(sessions), schema_store, snap_store)
        assert len(snap.forecast_threats.dominant_risk_patterns) <= 3

    # SS-23: empty pipeline returns empty dicts in forecast threats
    def test_ss23_empty_forecast_threats(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        snap = generate_snapshot(_MockRepo([]), schema_store, snap_store)
        assert snap.forecast_threats.top_failure_modes == {}
        assert snap.forecast_threats.active_strategy_interventions == {}
        assert snap.forecast_threats.dominant_risk_patterns == {}


# ---------------------------------------------------------------------------
class TestSnapshotRenderers:

    # SS-24: Markdown renderer contains all section headers
    def test_ss24_markdown_sections(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        from server.snapshot.renderer import render_markdown
        snap = generate_snapshot(_MockRepo([_make_session(amount=500_000)]), schema_store, snap_store)
        md = render_markdown(snap)
        assert "VICTROS PIPELINE RISK SNAPSHOT" in md
        assert "EXECUTIVE PIPELINE SNAPSHOT" in md
        assert "ACTIVE STRUCTURAL RISK" in md
        assert "FORECAST THREATS" in md

    # SS-25: HTML renderer produces valid HTML with all section markers
    def test_ss25_html_structure(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        from server.snapshot.renderer_html import render_html
        snap = generate_snapshot(_MockRepo([_make_session(amount=500_000, opportunity_id="Acme")]), schema_store, snap_store)
        html = render_html(snap)
        assert "<!DOCTYPE html>" in html
        assert "Pipeline Risk Snapshot" in html
        assert "Executive Pipeline Snapshot" in html
        assert "Active Structural Risk" in html
        assert "Forecast Threats" in html
        assert "Acme" in html

    # SS-26: HTML renderer bolds primary risk and lists secondary
    def test_ss26_html_risk_bold(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        from server.snapshot.renderer_html import render_html
        s = _make_session(lever_states={
            "case_for_change_strength": "WEAK",
            "champion_strength": "WEAK",
            "economic_buyer_commitment": "CONNECTED",
            "buyer_consensus": "CONNECTED",
            "decision_process_alignment": "CONNECTED",
            "differentiation_leverage": "CONNECTED",
            "buyer_urgency": "CONNECTED",
        })
        snap = generate_snapshot(_MockRepo([s]), schema_store, snap_store)
        html = render_html(snap)
        # Primary risk should be wrapped in risk-primary span
        cfcs = schema_store.get_lever("case_for_change_strength").name
        assert f'class="risk-primary">{cfcs}' in html

    # SS-27: HTML renderer shows N/A WoW on first run
    def test_ss27_html_wow_na(self, schema_store, snap_store):
        from server.snapshot.service import generate_snapshot
        from server.snapshot.renderer_html import render_html
        snap = generate_snapshot(_MockRepo([_make_session(amount=100_000)]), schema_store, snap_store)
        html = render_html(snap)
        assert "N/A WoW" in html

    # SS-28: snapshot store persists and retrieves correctly
    def test_ss28_store_roundtrip(self, tmp_path):
        from server.snapshot.models import PipelineSnapshotDocument
        from server.snapshot.store import FileSnapshotStore
        store = FileSnapshotStore(tmp_path / "snaps")
        doc = PipelineSnapshotDocument(
            id="test-id", snapshot_id="test-id",
            week_start="2026-04-06", week_end="2026-04-12",
            generated_at="2026-04-09T10:00:00+00:00",
            pipeline_value=1_000_000, active_deal_count=5,
            deals_at_risk_count=3, risks_resolved_count=8,
            pipeline_value_strengthened=400_000, deals_strengthened_count=2,
        )
        store.upsert(doc)
        assert store.get_by_week_start("2026-04-06").pipeline_value == 1_000_000
        assert store.get_latest().snapshot_id == "test-id"
