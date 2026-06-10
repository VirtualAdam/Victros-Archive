"""Renders a PipelineSnapshot to a self-contained HTML document.

Primary output format per the POC addendum. The file is fully self-contained
(no external CSS or JS dependencies) so it can be emailed, stored, or opened
directly in a browser. PDF export is a downstream step (e.g. Puppeteer).

Design language matches the Victros app: dark slate background, violet accent,
emerald for positive signals, red for risk. Executive-scannable in < 30 seconds.
"""
from __future__ import annotations

from server.snapshot.models import DealRiskEntry, PipelineSnapshot, WoWDelta


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_html(snapshot: PipelineSnapshot) -> str:
    week_label = f"{snapshot.week_start} — {snapshot.week_end}"
    body = "\n".join([
        _section_header(week_label),
        _section_metrics(snapshot),
        _section_deal_table(snapshot),
        _section_forecast(snapshot),
        _footer(snapshot),
    ])
    return _wrap_page(body, week_label)


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------

def _wrap_page(body: str, week_label: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Victros Pipeline Risk Snapshot — {week_label}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f172a;
    color: #cbd5e1;
    font-size: 14px;
    line-height: 1.6;
    padding: 48px 40px;
  }}
  .page {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 26px; font-weight: 700; color: #f1f5f9; letter-spacing: 0.04em; text-transform: uppercase; }}
  h2 {{ font-size: 13px; font-weight: 600; color: #94a3b8; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 4px; }}
  h3 {{ font-size: 13px; font-weight: 600; color: #94a3b8; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 10px; }}
  .divider {{ border: none; border-top: 1px solid #1e293b; margin: 36px 0; }}
  .intro {{ font-size: 13px; color: #64748b; line-height: 1.7; margin-top: 16px; }}
  /* Metric blocks */
  .metrics-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-top: 20px;
  }}
  .metric-block {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px 14px;
  }}
  .metric-label {{ font-size: 10px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px; }}
  .metric-value {{ font-size: 22px; font-weight: 700; color: #f1f5f9; line-height: 1.1; }}
  .metric-delta {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
  .delta-up {{ color: #34d399; }}
  .delta-down {{ color: #f87171; }}
  /* Deal table */
  .deal-card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 10px;
  }}
  .deal-header {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px; }}
  .deal-name {{ font-size: 15px; font-weight: 700; color: #f1f5f9; }}
  .deal-value {{ font-size: 13px; font-weight: 600; color: #a78bfa; }}
  .deal-meta {{ font-size: 12px; color: #64748b; margin-bottom: 10px; }}
  .deal-row {{ display: grid; grid-template-columns: 140px 1fr; gap: 6px; margin-bottom: 4px; font-size: 12px; }}
  .deal-row-label {{ color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding-top: 1px; }}
  .deal-row-value {{ color: #cbd5e1; }}
  .risk-primary {{ color: #f1f5f9; font-weight: 700; }}
  .risk-secondary {{ color: #94a3b8; }}
  /* Forecast threats */
  .threats-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-top: 20px;
  }}
  .threat-block {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px;
  }}
  .threat-title {{ font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 4px; }}
  .threat-subtitle {{ font-size: 10px; color: #475569; font-style: italic; margin-bottom: 12px; line-height: 1.4; }}
  .threat-row {{ display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid #1e293b; }}
  .threat-name {{ font-size: 12px; color: #cbd5e1; }}
  .threat-pct {{ font-size: 12px; font-weight: 700; color: #a78bfa; }}
  /* Footer */
  .footer {{ font-size: 10px; color: #334155; margin-top: 48px; text-align: center; letter-spacing: 0.05em; }}
  @media print {{
    body {{ background: #ffffff; color: #1e293b; padding: 24px; }}
    .metric-block, .deal-card, .threat-block {{ background: #f8fafc; border-color: #e2e8f0; }}
    .metric-value {{ color: #0f172a; }}
    .deal-name {{ color: #0f172a; }}
  }}
</style>
</head>
<body>
<div class="page">
{body}
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _section_header(week_label: str) -> str:
    return f"""
<h1>Victros Pipeline Risk Snapshot</h1>
<h2>Executive View of Structural Deal Risk and Intervention Progress</h2>
<p class="intro">
  <strong style="color:#94a3b8">Week of {week_label}</strong><br><br>
  Thank you for partnering in this category pilot of Victros — the first AI-native sales
  reasoning system. Victros works with your team as an expert in what must be true to win
  a deal, diagnosing what is missing and prescribing the highest-impact actions to resolve it.<br><br>
  This snapshot is not derived from CRM activity, engagement metrics, or statistical scoring.
  It is a system-generated view of structural truth extracted from live deal strategy —
  capturing what is preventing progress, how those risks are being addressed, and which
  buyer behaviors are shaping your outcomes.
</p>"""


def _section_metrics(snapshot: PipelineSnapshot) -> str:
    m = snapshot.metrics
    blocks = [
        _metric_block("Pipeline Value", _fmt_currency(m.pipeline_value), m.pipeline_value_delta, currency=True),
        _metric_block("Active Deals", str(m.active_deal_count), m.active_deal_count_delta),
        _metric_block(
            "Deals at Structural Risk",
            f"{m.deals_at_risk_count} <span style='font-size:14px;color:#94a3b8'>({_pct(m.deals_at_risk_count, m.active_deal_count)}%)</span>",
            m.deals_at_risk_delta,
        ),
        _metric_block("Structural Risks Resolved", str(m.risks_resolved_count), m.risks_resolved_delta),
        _metric_block(
            "Pipeline Value Strengthened",
            f"{_fmt_currency(m.pipeline_value_strengthened)} <span style='font-size:12px;color:#64748b'>across {m.deals_strengthened_count} deals</span>",
            m.pipeline_value_strengthened_delta,
            currency=True,
        ),
    ]
    return f"""
<hr class="divider">
<h3>Executive Pipeline Snapshot</h3>
<div class="metrics-grid">
{"".join(blocks)}
</div>"""


def _metric_block(label: str, value: str, delta: WoWDelta, currency: bool = False) -> str:
    delta_html = _delta_html(delta, currency)
    return f"""<div class="metric-block">
  <div class="metric-label">{label}</div>
  <div class="metric-value">{value}</div>
  <div class="metric-delta">{delta_html}</div>
</div>"""


def _section_deal_table(snapshot: PipelineSnapshot) -> str:
    if not snapshot.at_risk_deals:
        return """
<hr class="divider">
<h3>Active Structural Risk</h3>
<p style="color:#475569;font-size:13px;margin-top:12px;font-style:italic">No deals currently at structural risk.</p>"""

    cards = "".join(_deal_card(d) for d in snapshot.at_risk_deals)
    return f"""
<hr class="divider">
<h3>Active Structural Risk</h3>
<p style="font-size:11px;color:#475569;font-style:italic;margin-bottom:14px">
  Deals with at least one failed structural condition (lever = WEAK)
</p>
{cards}"""


def _deal_card(deal: DealRiskEntry) -> str:
    value_str = f"— {_fmt_currency(deal.deal_value)}" if deal.deal_value else ""
    zone_str = deal.zone_display or "—"
    strategy_str = deal.active_strategy or "Not set"
    next_move_str = deal.next_move or "No action selected yet"

    # Risk display: first entry is primary (bold), rest are secondary
    if deal.core_risks:
        primary = f'<span class="risk-primary">{deal.core_risks[0]}</span>'
        secondary = (
            f'; <span class="risk-secondary">{"; ".join(deal.core_risks[1:])}</span>'
            if len(deal.core_risks) > 1 else ""
        )
        risk_html = primary + secondary
    else:
        risk_html = '<span style="color:#475569">None identified</span>'

    return f"""<div class="deal-card">
  <div class="deal-header">
    <span class="deal-name">{deal.opportunity_id}</span>
    <span class="deal-value">{value_str}</span>
  </div>
  <div class="deal-meta">Owner: {deal.user_id}</div>
  <div class="deal-row"><span class="deal-row-label">Zone</span><span class="deal-row-value">{zone_str}</span></div>
  <div class="deal-row"><span class="deal-row-label">Core Risk</span><span class="deal-row-value">{risk_html}</span></div>
  <div class="deal-row"><span class="deal-row-label">Strategy</span><span class="deal-row-value">{strategy_str}</span></div>
  <div class="deal-row"><span class="deal-row-label">Next Move</span><span class="deal-row-value">{next_move_str}</span></div>
</div>"""


def _section_forecast(snapshot: PipelineSnapshot) -> str:
    ft = snapshot.forecast_threats

    failure_rows = "".join(
        f'<div class="threat-row"><span class="threat-name">{name}</span><span class="threat-pct">{pct}%</span></div>'
        for name, pct in ft.top_failure_modes.items()
    ) or '<p style="color:#475569;font-size:12px">No data</p>'

    strategy_rows = "".join(
        f'<div class="threat-row"><span class="threat-name">{name}</span><span class="threat-pct">{pct}%</span></div>'
        for name, pct in ft.active_strategy_interventions.items()
    ) or '<p style="color:#475569;font-size:12px">No data</p>'

    pattern_rows = "".join(
        f'<div class="threat-row"><span class="threat-name">{name}</span><span class="threat-pct">{pct}%</span></div>'
        for name, pct in ft.dominant_risk_patterns.items()
    ) or '<p style="color:#475569;font-size:12px">No data</p>'

    return f"""
<hr class="divider">
<h3>Forecast Threats</h3>
<div class="threats-grid">
  <div class="threat-block">
    <div class="threat-title">Top Failure Modes</div>
    <div class="threat-subtitle">% of deals where each structural condition required for deal success is currently missing</div>
    {failure_rows}
  </div>
  <div class="threat-block">
    <div class="threat-title">Active Strategy Interventions</div>
    <div class="threat-subtitle">% distribution of active strategy paths across all deals</div>
    {strategy_rows}
  </div>
  <div class="threat-block">
    <div class="threat-title">Dominant Risk Patterns</div>
    <div class="threat-subtitle">% of highest recurring buyer or deal behavior patterns in the pipeline</div>
    {pattern_rows}
  </div>
</div>"""


def _footer(snapshot: PipelineSnapshot) -> str:
    return f"""
<p class="footer">
  VICTROS · PIPELINE RISK SNAPSHOT · Generated {snapshot.generated_at[:10]} · Snapshot ID {snapshot.snapshot_id[:8]}
</p>"""


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


def _delta_html(delta: WoWDelta, currency: bool = False) -> str:
    if delta.value is None:
        return '<span style="color:#475569">N/A WoW</span>'
    if delta.value == 0:
        return '<span style="color:#475569">—</span>'
    sign = "+" if delta.value > 0 else ""
    css_class = "delta-up" if delta.value > 0 else "delta-down"
    if currency:
        abs_val = _fmt_currency(abs(delta.value))
        val_str = f"{'+' if delta.value > 0 else '-'}{abs_val}"
    else:
        val_str = f"{sign}{int(delta.value) if delta.value == int(delta.value) else delta.value}"
    return f'<span class="{css_class}">{val_str} WoW</span>'
