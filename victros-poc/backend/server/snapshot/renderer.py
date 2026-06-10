"""Renders a PipelineSnapshot to Markdown.

The output matches the fixed format in POC_Pipeline Risk Snapshot_MOCKUP.pdf:
  1. Header / intro copy
  2. Executive Pipeline Snapshot (metric blocks table)
  3. Active Structural Risk (deal table)
  4. Forecast Threats (data bullets)

All copy is deterministic — no LLM involved.
"""
from __future__ import annotations

from server.snapshot.models import DealRiskEntry, PipelineSnapshot, WoWDelta


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_markdown(snapshot: PipelineSnapshot) -> str:
    sections = [
        _render_header(snapshot),
        _render_metric_blocks(snapshot),
        _render_deal_table(snapshot),
        _render_forecast_threats(snapshot),
    ]
    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_header(snapshot: PipelineSnapshot) -> str:
    week_label = f"{snapshot.week_start} to {snapshot.week_end}"
    return (
        "# VICTROS PIPELINE RISK SNAPSHOT\n"
        "## Executive View of Structural Deal Risk and Intervention Progress\n\n"
        f"**Week of:** {week_label}  \n"
        f"**Generated:** {snapshot.generated_at[:10]}\n\n"
        "Thank you for partnering in this category pilot of Victros — the first "
        "AI-native sales reasoning system. Victros works with your team as an expert "
        "in what must be true to win a deal, diagnosing what is missing and prescribing "
        "the highest-impact actions to resolve it.\n\n"
        "This snapshot is not derived from CRM activity, engagement metrics, or "
        "statistical scoring. It is a system-generated view of structural truth extracted "
        "from live deal strategy — capturing what is preventing progress, how those risks "
        "are being addressed, and which buyer behaviors are shaping your outcomes.\n\n"
        "The following results reflect what rigorous deal inspection would reveal across "
        "every opportunity, while making visible the dominant patterns you can act on to "
        "improve both deal execution and go-to-market strategy."
    )


def _render_metric_blocks(snapshot: PipelineSnapshot) -> str:
    m = snapshot.metrics
    lines = [
        "## EXECUTIVE PIPELINE SNAPSHOT\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Pipeline Value | {_fmt_currency(m.pipeline_value)}{_delta_str(m.pipeline_value_delta, currency=True)} |",
        f"| Active Deals | {m.active_deal_count}{_delta_str(m.active_deal_count_delta)} |",
        f"| Deals at Structural Risk | {m.deals_at_risk_count} ({_pct(m.deals_at_risk_count, m.active_deal_count)}%){_delta_str(m.deals_at_risk_delta)} |",
        f"| Structural Risks Resolved | {m.risks_resolved_count}{_delta_str(m.risks_resolved_delta)} |",
        f"| Pipeline Value Strengthened | {_fmt_currency(m.pipeline_value_strengthened)} across {m.deals_strengthened_count} deals{_delta_str(m.pipeline_value_strengthened_delta, currency=True)} |",
    ]
    return "\n".join(lines)


def _render_deal_table(snapshot: PipelineSnapshot) -> str:
    if not snapshot.at_risk_deals:
        return (
            "## ACTIVE STRUCTURAL RISK\n\n"
            "_No deals currently at structural risk._"
        )

    lines = [
        "## ACTIVE STRUCTURAL RISK\n",
        "_Deals with at least one failed structural condition (lever = WEAK)_\n",
    ]
    for deal in snapshot.at_risk_deals:
        lines.append(_render_deal_entry(deal))

    return "\n".join(lines)


def _render_deal_entry(deal: DealRiskEntry) -> str:
    value_str = f" — {_fmt_currency(deal.deal_value)}" if deal.deal_value else ""
    risks_str = "; ".join(deal.core_risks) if deal.core_risks else "None identified"
    # Bold the first (primary) risk to match mockup style
    if deal.core_risks:
        bolded = [f"**{deal.core_risks[0]}**"] + deal.core_risks[1:]
        risks_str = "; ".join(bolded)

    lines = [
        f"### {deal.opportunity_id}{value_str}",
        f"**Owner:** {deal.user_id}  ",
    ]
    if deal.zone_display:
        lines.append(f"**Zone:** {deal.zone_display}  ")
    lines += [
        f"**Core Structural Risk:** {risks_str}  ",
        f"**Active Strategy:** {deal.active_strategy or 'Not set'}  ",
        f"**Next Move:** {deal.next_move or 'No action selected yet'}",
        "",
    ]
    return "\n".join(lines)


def _render_forecast_threats(snapshot: PipelineSnapshot) -> str:
    ft = snapshot.forecast_threats
    lines = ["## FORECAST THREATS\n"]

    lines.append("**Top Failure Modes**  ")
    lines.append("_% of deals where each structural condition (lever) is missing_  ")
    if ft.top_failure_modes:
        for name, pct in ft.top_failure_modes.items():
            lines.append(f"- {name} — {pct}%")
    else:
        lines.append("- No failure modes identified")

    lines += ["", "**Active Strategy Interventions**  ",
              "_% distribution of active strategy paths across all deals_  "]
    if ft.active_strategy_interventions:
        for name, pct in ft.active_strategy_interventions.items():
            lines.append(f"- {name} — {pct}%")
    else:
        lines.append("- No active strategies")

    lines += ["", "**Dominant Risk Patterns**  ",
              "_% of deals exhibiting each pattern_  "]
    if ft.dominant_risk_patterns:
        for name, pct in ft.dominant_risk_patterns.items():
            lines.append(f"- {name} — {pct}%")
    else:
        lines.append("- No patterns identified")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_currency(value: float | None) -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0"
    return str(round(part / total * 100))


def _delta_str(delta: WoWDelta, currency: bool = False) -> str:
    if delta.value is None:
        return " _(N/A WoW)_"
    sign = "+" if delta.value > 0 else ""
    if currency:
        val_str = f"{sign}{_fmt_currency(abs(delta.value))}"
        if delta.value < 0:
            val_str = f"-{_fmt_currency(abs(delta.value))}"
    else:
        val_str = f"{sign}{int(delta.value)}" if isinstance(delta.value, float) and delta.value == int(delta.value) else f"{sign}{delta.value}"
    return f" _({val_str} WoW)_"
