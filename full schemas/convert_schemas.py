"""Convert SRS CSV schema files to JSON files for the Victros POC.

Run from the 'full schemas' directory:
    python3 convert_schemas.py

Outputs to: ../victros-poc/backend/schema/
"""
from __future__ import annotations

import csv
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent / "victros-poc" / "backend" / "schema"
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv(fname: str) -> list[list[str]]:
    with open(HERE / fname, encoding="utf-8") as f:
        return list(csv.reader(f))


def split_list(s: str) -> list[str]:
    """Split a comma or newline-separated cell into a cleaned list, skipping empties."""
    if not s or not s.strip():
        return []
    # Normalize newlines to commas first
    s = s.replace("\n", ",")
    return [item.strip() for item in s.split(",") if item.strip()]


def to_key(name: str) -> str:
    """Convert a display name to a snake_case key."""
    s = name.strip()
    s = re.sub(r"[^a-zA-Z0-9\s_-]", "", s)
    s = re.sub(r"[\s\-]+", "_", s)
    return s.lower()


# Canonical lever display name → snake_case key map
_LEVER_NAME_TO_KEY = {
    "Case for Change Strength": "case_for_change_strength",
    "Differentiation Leverage": "differentiation_leverage",
    "Champion Strength": "champion_strength",
    "Economic Buyer Commitment": "economic_buyer_commitment",
    "Buyer Consensus": "buyer_consensus",
    "Decision Process Alignment": "decision_process_alignment",
    "Buyer Urgency": "buyer_urgency",
}


def normalize_lever(name: str) -> str:
    """Map a lever display name to its canonical snake_case key."""
    name = name.strip()
    return _LEVER_NAME_TO_KEY.get(name, to_key(name))


def normalize_zone(name: str) -> str:
    """Normalize Zone1/Zone2/zone1/zone2 → zone1/zone2."""
    return name.strip().lower().replace(" ", "")


def write_json(name: str, data) -> None:
    path = OUT / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ {name}  ({len(data)} items)")


# ---------------------------------------------------------------------------
# 1. Signals
# ---------------------------------------------------------------------------

def convert_signals():
    rows = read_csv("Copy of SRS POC_Core Schema - SLF Schema-Signals.csv")
    # row 0: blank, 1: headers, 2: Purpose, 3: Instructions, 4+: data
    data_rows = [r for r in rows[4:] if r[0].strip() and r[0].strip() not in ("Purpose", "Instructions", "UXState")]

    out = []
    for r in data_rows:
        name = r[0].strip()
        key = to_key(name)
        polarity = r[3].strip().lower()  # POSITIVE/NEGATIVE → positive/negative
        signal_type_raw = r[5].strip()
        # Map verbose type to schema type values
        if "structural" in signal_type_raw.lower() and "risk" in signal_type_raw.lower():
            signal_type = "structural_risk"
        elif "momentum" in signal_type_raw.lower() and "risk" in signal_type_raw.lower():
            signal_type = "momentum_risk"
        elif "structural" in signal_type_raw.lower():
            signal_type = "structural_strength"
        else:
            signal_type = "momentum_strength"

        out.append({
            "key": key,
            "name": name,
            "description": r[1].strip(),
            "observable_condition": r[2].strip(),
            "polarity": polarity,
            "severity": r[4].strip().upper(),
            "type": signal_type,
            "affected_levers": [normalize_lever(l) for l in split_list(r[6])],
            "zone_bias": [normalize_zone(z) for z in split_list(r[7])],
            "trigger_input_conditions": r[8].strip(),
            "target_patterns": split_list(r[9]),
        })

    write_json("signals.json", out)
    return out


# ---------------------------------------------------------------------------
# 2. Patterns
# ---------------------------------------------------------------------------

def convert_patterns(signal_name_to_key: dict[str, str]):
    rows = read_csv("Copy of SRS POC_Core Schema - SLF Schema-Patterns.csv")
    data_rows = [r for r in rows[5:] if r[0].strip() and r[0].strip() not in ("Purpose", "Instructions", "UXState")]

    out = []
    for r in data_rows:
        name = r[0].strip()
        key = to_key(name)

        # PatternType: normalize
        type_raw = r[7].strip()
        if "structural" in type_raw.lower() and "risk" in type_raw.lower():
            pat_type = "structural_risk"
        elif "momentum" in type_raw.lower() and "risk" in type_raw.lower():
            pat_type = "momentum_risk"
        elif "structural" in type_raw.lower():
            pat_type = "structural_strength"
        else:
            pat_type = "momentum_strength"

        # Trigger signals: stored as display names → convert to keys
        trigger_raw = split_list(r[3])
        trigger_keys = []
        for t in trigger_raw:
            resolved = signal_name_to_key.get(t)
            if resolved:
                trigger_keys.append(resolved)
            else:
                # Fallback: try to_key conversion
                trigger_keys.append(to_key(t))

        out.append({
            "key": key,
            "name": name,
            "description": r[1].strip(),
            "summary": r[2].strip(),
            "trigger_signals": trigger_keys,
            "diagnostic_questions": [q.strip() + "?" for q in r[4].split("?") if q.strip()] if r[4].strip() else [],
            "root_cause_themes": split_list(r[5]),
            "polarity": r[6].strip().lower(),
            "type": pat_type,
            "severity": r[8].strip().upper(),
            "resolution_type": r[9].strip().upper(),
            "zone_bias": [normalize_zone(z) for z in split_list(r[10])],
            "affected_levers": [normalize_lever(l) for l in split_list(r[11])],
            "candidate_strategy_path_keys": split_list(r[12]),
        })

    write_json("patterns.json", out)
    return out


# ---------------------------------------------------------------------------
# 3. Strategy Paths
# ---------------------------------------------------------------------------

def convert_strategy_paths():
    rows = read_csv("Copy of SRS POC_Core Schema - SLF Schema-StrategyPaths.csv")
    data_rows = [r for r in rows[5:] if r[0].strip() and r[0].strip() not in ("Purpose", "Instructions", "UXState")]

    out = []
    for r in data_rows:
        # Pad short rows
        while len(r) < 26:
            r.append("")

        key = r[0].strip()

        # RepresentativeActions: comma-separated action descriptions → generate keys
        rep_actions_raw = r[17].strip()
        rep_action_keys = []
        if rep_actions_raw:
            for action in rep_actions_raw.split(","):
                action = action.strip()
                if action:
                    rep_action_keys.append({"key": to_key(action[:50]), "ux_text": action})

        out.append({
            "key": key,
            "display_name": r[1].strip(),
            "description": r[2].strip(),
            "mode": r[3].strip().upper(),
            "diagnostic_question": r[4].strip(),
            "activation_polarity": r[5].strip().upper(),
            "target_levers": [normalize_lever(l) for l in split_list(r[6])],
            "dominant_failure_mode": r[7].strip(),
            "zone_bias": [normalize_zone(z) for z in split_list(r[8])],
            "primary_target_pattern": r[9].strip(),
            "target_patterns": split_list(r[10]),
            "entry_conditions": split_list(r[11]),
            "disqualifying_conditions": split_list(r[12]),
            "core_objectives": r[13].strip(),
            "strategic_focus": r[14].strip(),
            "core_strategies": [s.strip() for s in r[15].split(",") if s.strip()],
            "prohibited_strategies": [s.strip() for s in r[16].split(",") if s.strip()],
            "representative_actions": [a["key"] for a in rep_action_keys],
            "champion_required_behavior": r[18].strip(),
            "economic_buyer_required_behavior": r[19].strip(),
            "positive_progress_signals": split_list(r[20]),
            "negative_progress_signals": split_list(r[21]),
            "exit_lever_state": r[22].strip(),
            "exit_outcome": r[23].strip(),
            "transition_signals": split_list(r[24]),
            "operator_notes": r[25].strip(),
        })

    write_json("strategy_paths.json", out)

    # Also build representative_actions.json from inline action data
    actions = []
    for sp in out:
        for r in rows[5:]:
            if r[0].strip() != sp["key"]:
                continue
            while len(r) < 18:
                r.append("")
            rep_actions_raw = r[17].strip()
            if not rep_actions_raw:
                continue
            for action_text in rep_actions_raw.split(","):
                action_text = action_text.strip()
                if action_text:
                    actions.append({
                        "action_key": to_key(action_text[:50]),
                        "parent_strategy_path": sp["key"],
                        "description": action_text,
                        "ux_text": action_text,
                    })
    write_json("representative_actions.json", actions)

    return out


# ---------------------------------------------------------------------------
# 4. Levers
# ---------------------------------------------------------------------------

def convert_levers():
    rows = read_csv("Copy of SRS POC_Core Schema - SLF Schema-Levers.csv")
    # row 0: blank, 1: section header, 2: column headers, 3: col descriptions, 4+: data
    data_rows = [r for r in rows[4:] if r[0].strip()]

    out = []
    for r in data_rows:
        name = r[0].strip()
        key = to_key(name)
        out.append({
            "key": key,
            "name": name,
            "qualifiers": r[1].strip(),
            "score_model": r[2].strip(),
            "lever_scoring": r[3].strip(),
            "why_it_matters": r[4].strip(),
            "states": ["WEAK", "CONNECTED", "COMMITTED", "EXECUTING"],
        })

    write_json("levers.json", out)
    return out


# ---------------------------------------------------------------------------
# 5. Sales Zones
# ---------------------------------------------------------------------------

def convert_sales_zones():
    rows = read_csv("Copy of SRS POC_Core Schema - RLF (Deterministic Rules) Schema-SalesZones.csv")
    # row 0: blank, 1: headers, 2: col descriptions, 3+: data
    data_rows = [r for r in rows[3:] if r[0].strip() and not r[0].strip().startswith("Unique")]

    out = []
    for r in data_rows:
        while len(r) < 12:
            r.append("")
        key = r[0].strip().lower()
        out.append({
            "key": key,
            "display_name": r[1].strip(),
            "buyer_type": r[2].strip(),
            "purpose": r[3].strip(),
            "core_objectives": r[4].strip(),
            "core_strategies": r[5].strip(),
            "strategy_method": r[6].strip(),
            "core_actions": r[7].strip(),
            "minimum_required_lever_states": r[8].strip(),
            "zone_risk_lever_triggers": r[9].strip(),
            "qualification_requirements": split_list(r[10]),
            "qualification_guidance": r[11].strip(),
        })

    write_json("sales_zones.json", out)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Converting SRS CSV schemas → JSON...")
    signals = convert_signals()
    # Build name → key map for cross-reference resolution
    signal_name_to_key = {s["name"]: s["key"] for s in signals}
    patterns = convert_patterns(signal_name_to_key)
    strategy_paths = convert_strategy_paths()
    levers = convert_levers()
    zones = convert_sales_zones()
    print(f"\nDone. Schema summary:")
    print(f"  Signals:         {len(signals)}")
    print(f"  Patterns:        {len(patterns)}")
    print(f"  Strategy Paths:  {len(strategy_paths)}")
    print(f"  Levers:          {len(levers)}")
    print(f"  Sales Zones:     {len(zones)}")
