"""Deterministic Decision Engine — Pure Python, No LLM.

This is the core of Victros. Given a set of confirmed active signals,
it determines the priority pattern, selects a strategy path, and
surfaces representative actions.

Pipeline steps (from data-flow-logic.md Part 2):
  E1 — Signal Activation (signals carry target_patterns)
  E2 — Signal-to-Pattern Mapping (signal-driven, not AND-gated)
  E3 — PatternWeight Computation (signal authority flows into patterns)
  E4 — Priority Pattern Selection (6-step deterministic tiebreaker)
  E5 — Secondary Pattern Assignment
  E6 — StrategyPath Selection
"""
from __future__ import annotations

import re

from server.models import ActiveSignal, DecisionResult, Pattern, RepresentativeAction, Signal, StrategyPath
from server.schema_store import SchemaStore

# Canonical lever ordering — per spec 1.6 tiebreaker.
LEVER_ORDER = [
    "case_for_change_strength",
    "champion_strength",
    "economic_buyer_commitment",
    "decision_process_alignment",
    "buyer_consensus",
    "differentiation_leverage",
    "buyer_urgency",
]

ZONE_ORDER = [
    "zone1",
    "zone2",
    "zone3",
    "zone4",
]

# Severity weights for PatternWeight computation (spec 1.5).
SEVERITY_WEIGHT = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}

# PatternWeight constants (data-flow-logic.md Part 2 E3).
STRUCTURAL_BONUS = 1.0
LEVER_WEIGHT = 1.0
STRUCTURAL_TYPES = {"structural_risk", "structural_strength"}


def density_factor(n: int) -> float:
    """Each additional signal beyond the first adds 0.5."""
    return (n - 1) * 0.5 if n > 1 else 0.0


def _check_trigger_conditions(
    trigger_text: str, intake_fields: dict[str, str]
) -> bool:
    """Check if intake_fields satisfy a signal's trigger_input_conditions.

    Uses a simple heuristic: extract field-name references from the trigger
    text and verify the corresponding intake field is present and non-empty.
    Returns True if conditions are met (or if no field references found).
    """
    if not trigger_text:
        return True

    # Build a map from normalised field names to their intake values
    normalised_fields: dict[str, str] = {}
    for k, v in intake_fields.items():
        norm = k.lower().replace("_", " ").strip()
        normalised_fields[norm] = str(v).strip() if v else ""

    # Split on AND/OR to get individual clauses
    clauses = re.split(r"\s+AND\s+|\s+OR\s+", trigger_text, flags=re.IGNORECASE)

    eq_refs: list[tuple[str, str]] = []
    field_refs: list[str] = []
    for clause in clauses:
        clause = clause.strip()
        # "FieldName = Value" pattern
        eq_match = re.match(
            r"([a-zA-Z][a-zA-Z_ ]+?)\s*=\s*(.+)", clause, re.IGNORECASE
        )
        if eq_match:
            eq_refs.append((eq_match.group(1).lower().strip(),
                            eq_match.group(2).lower().strip().rstrip(".")))
            continue
        # "FieldName field empty/populated" pattern
        field_match = re.search(
            r"([a-zA-Z][a-zA-Z_ ]+?)\s+field", clause, re.IGNORECASE
        )
        if field_match:
            field_refs.append(field_match.group(1).lower().strip())
            continue
        # "FieldName indicates ..." pattern — just check field is present
        indicates_match = re.match(
            r"([a-zA-Z][a-zA-Z_ ]+?)\s+(?:indicates|reflects|shows|confirms)",
            clause, re.IGNORECASE,
        )
        if indicates_match:
            field_name = indicates_match.group(1).lower().strip()
            intake_val = normalised_fields.get(field_name, "")
            if not intake_val:
                return False

    if not eq_refs and not field_refs:
        return True

    for field_name, expected_value in eq_refs:
        intake_val = normalised_fields.get(field_name, "")
        if not intake_val:
            return False
        if expected_value not in intake_val.lower():
            return False

    for field_name in field_refs:
        intake_val = normalised_fields.get(field_name, "")
        if field_name == "measurable impact":
            continue
        if not intake_val:
            return False

    return True


def detect_signal_gaps(
    active_signal_keys: list[str],
    schema_store: SchemaStore,
) -> list[dict]:
    """Detect lever coverage gaps in the active signal set.

    Returns a list of gap dicts, each with:
      - lever_name: str
      - gap_type: "uncovered" | "polarity_imbalance"
      - severity: "critical" | "warning"
      - missing_signal_keys: list[str]  (signals that could fill the gap)
    """
    lever_positive: dict[str, list[str]] = {lk: [] for lk in LEVER_ORDER}
    lever_negative: dict[str, list[str]] = {lk: [] for lk in LEVER_ORDER}

    for key in active_signal_keys:
        sig = schema_store.get_signal(key)
        if sig is None:
            continue
        for lever in sig.affected_levers:
            if lever not in lever_positive:
                continue
            if sig.polarity == "positive":
                lever_positive[lever].append(key)
            else:
                lever_negative[lever].append(key)

    lever_has_critical: dict[str, bool] = {lk: False for lk in LEVER_ORDER}
    lever_all_signals: dict[str, list[str]] = {lk: [] for lk in LEVER_ORDER}
    for sig in schema_store.signals:
        for lever in sig.affected_levers:
            if lever in lever_all_signals:
                lever_all_signals[lever].append(sig.key)
                if sig.severity == "CRITICAL":
                    lever_has_critical[lever] = True

    gaps: list[dict] = []
    for lever in LEVER_ORDER:
        covered_pos = lever_positive[lever]
        covered_neg = lever_negative[lever]
        total_covered = covered_pos + covered_neg

        if not total_covered:
            severity = "critical" if lever_has_critical[lever] else "warning"
            gaps.append({
                "lever_name": lever,
                "gap_type": "uncovered",
                "severity": severity,
                "missing_signal_keys": lever_all_signals[lever],
            })
        elif covered_neg and not covered_pos:
            positive_signals = [
                s.key for s in schema_store.signals
                if lever in s.affected_levers and s.polarity == "positive"
            ]
            gaps.append({
                "lever_name": lever,
                "gap_type": "polarity_imbalance",
                "severity": "warning",
                "missing_signal_keys": positive_signals,
            })

    return gaps


def validate_signals(
    candidate_signals: list[dict],
    intake_fields: dict,
    schema_store: SchemaStore,
) -> list[ActiveSignal]:
    """Validate candidate signals against structural preconditions,
    confidence thresholds, and evidence requirements.

    Each candidate_signal dict: {key, confidence, evidence_text, source}
    Returns list of ActiveSignal objects that pass all validation gates.
    """
    result: list[ActiveSignal] = []

    for candidate in candidate_signals:
        key = candidate.get("key", "")
        confidence = candidate.get("confidence", 0.0)
        evidence_text = candidate.get("evidence_text")
        source = candidate.get("source", "system")

        signal_def = schema_store.get_signal(key)
        if signal_def is None:
            continue

        # Gate 1: Structural preconditions
        if not _check_trigger_conditions(
            signal_def.trigger_input_conditions, intake_fields
        ):
            continue

        # Gate 2: Confidence threshold
        if confidence < signal_def.confidence_threshold:
            continue

        # Gate 3: Evidence requirement
        if signal_def.requires_evidence and signal_def.severity in ("CRITICAL", "HIGH"):
            if not evidence_text or not evidence_text.strip():
                continue

        result.append(ActiveSignal(
            key=key,
            confidence=confidence,
            evidence_text=evidence_text,
            source=source,
        ))

    return result


class DecisionEngine:
    """Stateless decision engine. Every call to `run()` is independent."""

    def __init__(self, schema: SchemaStore) -> None:
        self.schema = schema

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        active_signals: list[str],
        deal_stage: str,
        excluded_patterns: list[str] | None = None,
        enforce_quality_gates: bool = False,
    ) -> DecisionResult:
        """Execute the full pipeline and return a DecisionResult.

        When *enforce_quality_gates* is True, a critical lever-coverage gap
        blocks pattern prioritization and returns gap_blocked=True.
        """
        lever_states = self.evaluate_signals(active_signals)

        zone = self.schema.get_zone_for_stage(deal_stage)
        zone_key = zone.key if zone else "zone2"

        # Signal Quality Gate: detect coverage gaps before pattern activation
        quality_gaps = detect_signal_gaps(active_signals, self.schema)
        has_critical_gap = any(
            g["gap_type"] == "uncovered" and g.get("severity") == "critical"
            for g in quality_gaps
        )
        gap_warnings = quality_gaps if quality_gaps else []

        if enforce_quality_gates and has_critical_gap:
            return DecisionResult(
                primary_pattern=None,
                secondary_patterns=[],
                strategy_path=None,
                representative_actions=[],
                active_signals=active_signals,
                lever_states=lever_states,
                zone=zone_key,
                signal_quality_warnings=gap_warnings,
                gap_blocked=True,
            )

        # E1 + E2: Map signals to patterns
        signal_objects = self._resolve_signals(active_signals)
        activated = self.activate_patterns_from_signals(signal_objects)

        # Filter out excluded patterns (used by address_next_issue)
        _excluded = set(excluded_patterns or [])
        if _excluded:
            activated = [p for p in activated if p.key not in _excluded]

        if not activated:
            return DecisionResult(
                primary_pattern=None,
                secondary_patterns=[],
                strategy_path=None,
                representative_actions=[],
                active_signals=active_signals,
                lever_states=lever_states,
                zone=zone_key,
                signal_quality_warnings=gap_warnings,
            )

        # E3: Compute PatternWeight
        pattern_weights = self.compute_pattern_weights(activated, signal_objects, lever_states)

        # Part 5: Sufficiency check
        sufficient = [p for p in activated if self.sufficient_authority(p, signal_objects)]
        if not sufficient:
            return DecisionResult(
                primary_pattern=None,
                secondary_patterns=[],
                strategy_path=None,
                representative_actions=[],
                active_signals=active_signals,
                lever_states=lever_states,
                zone=zone_key,
                signal_quality_warnings=gap_warnings,
            )

        # E4: Priority Pattern Selection
        primary = self.select_priority_pattern(sufficient, pattern_weights)

        # E5: Secondary patterns
        secondary = [p for p in activated if p.key != primary.key]

        # E6: StrategyPath selection
        sp = self.select_strategy_path(primary, active_signals, zone_key)
        actions = self.get_actions(sp) if sp else []

        return DecisionResult(
            primary_pattern=primary.key,
            secondary_patterns=[p.key for p in secondary],
            strategy_path=sp.key if sp else None,
            representative_actions=[a.action_key for a in actions],
            active_signals=active_signals,
            lever_states=lever_states,
            zone=zone_key,
            signal_quality_warnings=gap_warnings,
        )

    # ------------------------------------------------------------------
    # E1: Signal Evaluation (lever states)
    # ------------------------------------------------------------------
    def evaluate_signals(self, active_signal_keys: list) -> dict[str, str]:
        """Compute lever states from active signals.

        Accepts list[str] (signal keys) or list[ActiveSignal/dict] for
        backward compatibility.  Positive signals advance levers WEAK → CONNECTED.
        """
        lever_states = {lk: "WEAK" for lk in LEVER_ORDER}

        # Normalise to plain string keys
        keys: list[str] = []
        for item in active_signal_keys:
            if isinstance(item, str):
                keys.append(item)
            elif isinstance(item, ActiveSignal):
                keys.append(item.key)
            elif isinstance(item, dict) and "key" in item:
                keys.append(item["key"])
            else:
                keys.append(str(item))

        for sig_key in keys:
            signal = self.schema.get_signal(sig_key)
            if signal is None:
                continue
            if signal.polarity == "positive":
                for lever_key in signal.affected_levers:
                    if lever_key in lever_states and lever_states[lever_key] == "WEAK":
                        lever_states[lever_key] = "CONNECTED"

        return lever_states

    # ------------------------------------------------------------------
    # E2: Signal-to-Pattern Mapping (signal-driven activation)
    # ------------------------------------------------------------------
    def activate_patterns_from_signals(
        self, signals: list[Signal]
    ) -> list[Pattern]:
        """Activate patterns by mapping signals to their target_patterns.

        A pattern is activated when at least one active signal targets it.
        This is signal-driven (OR logic), not the old AND-gated model.
        """
        targeted_keys: set[str] = set()
        for signal in signals:
            for pk in signal.target_patterns:
                targeted_keys.add(pk)

        activated: list[Pattern] = []
        for pattern in self.schema.patterns:
            if pattern.key in targeted_keys:
                activated.append(pattern)
        return activated

    def activate_patterns(self, active_signal_keys: list[str]) -> list[Pattern]:
        """Legacy activation — kept for backward compatibility with tests.

        Uses trigger_signals (AND-gated) as fallback when target_patterns
        is empty, but prefers signal-driven activation.
        """
        signals = self._resolve_signals(active_signal_keys)
        activated = self.activate_patterns_from_signals(signals)
        if activated:
            return activated

        # Fallback: old AND-gated logic for schemas without target_patterns
        signal_set = set(active_signal_keys)
        fallback: list[Pattern] = []
        for pattern in self.schema.patterns:
            if pattern.trigger_signals and all(
                ts in signal_set for ts in pattern.trigger_signals
            ):
                fallback.append(pattern)
        return fallback

    # ------------------------------------------------------------------
    # E3: PatternWeight Computation
    # ------------------------------------------------------------------
    def compute_pattern_weights(
        self,
        patterns: list[Pattern],
        signals: list[Signal],
        lever_states: dict[str, str],
    ) -> dict[str, float]:
        """Compute PatternWeight for each activated pattern per spec 1.5."""
        # Group signals by target pattern
        pattern_signals: dict[str, list[Signal]] = {p.key: [] for p in patterns}
        for signal in signals:
            for pk in signal.target_patterns:
                if pk in pattern_signals:
                    pattern_signals[pk].append(signal)

        # Find weakest lever
        lever_score = {
            "WEAK": 1, "CONNECTED": 2, "COMMITTED": 3, "EXECUTING": 4,
        }
        weakest_lever = min(
            LEVER_ORDER,
            key=lambda lk: lever_score.get(lever_states.get(lk, "WEAK"), 1),
        )

        weights: dict[str, float] = {}
        for p in patterns:
            contributing = pattern_signals.get(p.key, [])
            if not contributing:
                weights[p.key] = 0.0
                continue

            # Highest severity weight among contributing signals
            highest_sev = max(
                SEVERITY_WEIGHT.get(s.severity, 1) for s in contributing
            )

            # Structural bonus
            has_structural = any(s.type in STRUCTURAL_TYPES for s in contributing)
            structural = STRUCTURAL_BONUS if has_structural else 0.0

            # Density factor
            density = density_factor(len(contributing))

            # Weakest lever bonus
            targets_weakest = weakest_lever in p.affected_levers
            lever_bonus = LEVER_WEIGHT if targets_weakest else 0.0

            weights[p.key] = highest_sev + structural + density + lever_bonus

        return weights

    # ------------------------------------------------------------------
    # Part 5: Pattern Activation Sufficiency
    # ------------------------------------------------------------------
    def sufficient_authority(self, pattern: Pattern, signals: list[Signal]) -> bool:
        """Check if a pattern has sufficient signal authority to be Priority Pattern."""
        contributing = [
            s for s in signals
            if pattern.key in s.target_patterns
        ]
        # Has at least one structural signal
        if any(s.type in STRUCTURAL_TYPES for s in contributing):
            return True
        # OR has 2+ HIGH/CRITICAL signals
        high_crit = [s for s in contributing if SEVERITY_WEIGHT.get(s.severity, 1) >= 3]
        return len(high_crit) >= 2

    # ------------------------------------------------------------------
    # E4: Priority Pattern Selection (6-step tiebreaker)
    # ------------------------------------------------------------------
    def select_priority_pattern(
        self,
        patterns: list[Pattern],
        weights: dict[str, float],
    ) -> Pattern:
        """Select exactly one Priority Pattern using 6-step deterministic order."""
        if len(patterns) == 1:
            return patterns[0]

        def sort_key(p: Pattern) -> tuple:
            # Step 1: PatternWeight (higher = better → negate for sort)
            w = -weights.get(p.key, 0.0)

            # Step 2: PatternSeverity
            sev = -SEVERITY_WEIGHT.get(p.severity, 1)

            # Step 3: Structural Precedence
            type_order = {
                "structural_risk": 4, "structural_strength": 3,
                "momentum_risk": 2, "momentum_strength": 1,
            }
            struct = -type_order.get(p.type, 0)

            # Step 4: Lever Priority (earlier = higher priority)
            lever_idx = min(
                (LEVER_ORDER.index(lk) for lk in p.affected_levers if lk in LEVER_ORDER),
                default=99,
            )

            # Step 5: Earliest Zone
            zone_biases = p.zone_bias if isinstance(p.zone_bias, list) else [p.zone_bias]
            zone_idx = min(
                (ZONE_ORDER.index(z) for z in zone_biases if z in ZONE_ORDER),
                default=99,
            )

            return (w, sev, struct, lever_idx, zone_idx)

        sorted_patterns = sorted(patterns, key=sort_key)
        return sorted_patterns[0]

    # ------------------------------------------------------------------
    # Legacy: resolve_collisions (wraps new logic for backward compat)
    # ------------------------------------------------------------------
    def resolve_collisions(
        self, patterns: list[Pattern]
    ) -> tuple[Pattern, list[Pattern]]:
        """Return (primary, secondaries) — wraps the new PatternWeight-aware logic."""
        if len(patterns) == 1:
            return patterns[0], []

        # If called without weights (legacy path), compute them
        signals = []
        for p in patterns:
            for s in self.schema.signals:
                if p.key in s.target_patterns and s not in signals:
                    signals.append(s)

        lever_states = {lk: "WEAK" for lk in LEVER_ORDER}
        weights = self.compute_pattern_weights(patterns, signals, lever_states)
        primary = self.select_priority_pattern(patterns, weights)
        secondary = [p for p in patterns if p.key != primary.key]
        return primary, secondary

    # ------------------------------------------------------------------
    # E6: StrategyPath Selection
    # ------------------------------------------------------------------
    def select_strategy_path(
        self,
        pattern: Pattern,
        active_signals: list,
        zone_key: str,
        lever_states: dict[str, str] | None = None,
    ):
        """Select the best strategy path for the given pattern.

        When *lever_states* is provided, candidates that survive the
        disqualification / entry-condition gate are ranked by a composite
        score (lever alignment + resolution-type match + entry-condition
        strength).  Without *lever_states* the legacy first-match behaviour
        is preserved for backward compatibility.
        """
        # Normalise to plain string keys for set lookup
        signal_set: set[str] = set()
        for item in active_signals:
            if isinstance(item, str):
                signal_set.add(item)
            elif isinstance(item, ActiveSignal):
                signal_set.add(item.key)
            elif isinstance(item, dict) and "key" in item:
                signal_set.add(item["key"])
            else:
                signal_set.add(str(item))
        candidates = []

        for sp_key in pattern.candidate_strategy_path_keys:
            sp = self.schema.get_strategy_path(sp_key)
            if sp is None:
                continue

            # Disqualifying conditions
            disqualifying_signal_keys = [
                dc for dc in sp.disqualifying_conditions if self._looks_like_signal_key(dc)
            ]
            if any(dc in signal_set for dc in disqualifying_signal_keys):
                continue

            # Entry conditions
            entry_signal_keys = [
                ec for ec in sp.entry_conditions if self._looks_like_signal_key(ec)
            ]
            if entry_signal_keys and not any(ec in signal_set for ec in entry_signal_keys):
                continue

            candidates.append(sp)

        if not candidates:
            return None

        # Legacy first-match when no lever context supplied.
        if lever_states is None:
            return candidates[0]

        # --- Ranked selection ---
        def _score(sp):
            return (
                self._lever_alignment_score(sp, lever_states)
                + self._resolution_match_score(sp, pattern)
                + self._entry_condition_strength(sp, signal_set)
            )

        candidates.sort(key=_score, reverse=True)
        return candidates[0]

    # ------------------------------------------------------------------
    # Ranking helpers
    # ------------------------------------------------------------------

    _LEVER_STATE_POINTS = {"WEAK": 2, "CONNECTED": 1}

    def _lever_alignment_score(self, sp, lever_states: dict[str, str]) -> int:
        """Score 0-5: value this path delivers given current lever weakness.

        The first (primary) target lever is double-weighted. Capped at 5.
        """
        points = []
        for lever in sp.target_levers:
            state = lever_states.get(lever, "COMMITTED")
            points.append(self._LEVER_STATE_POINTS.get(state, 0))
        if not points:
            return 0
        raw = points[0] * 2 + sum(points[1:])
        return min(raw, 5)

    def _resolution_match_score(self, sp, pattern: Pattern) -> int:
        """Score 0-3: how well the path's mode fits the pattern's resolution type."""
        if sp.mode == pattern.resolution_type:
            return 3
        p_type = pattern.type.lower()
        severity = pattern.severity.upper()
        if "risk" in p_type and sp.mode == "RECOVER":
            return 1
        if "strength" in p_type and sp.mode == "ADVANCE":
            return 1
        if sp.mode == "EXIT" and severity == "CRITICAL":
            return 1
        return 0

    def _entry_condition_strength(self, sp, signal_set: set[str]) -> int:
        """Count how many signal-key entry conditions are currently satisfied."""
        return sum(
            1 for ec in sp.entry_conditions
            if self._looks_like_signal_key(ec) and ec in signal_set
        )

    # ------------------------------------------------------------------
    # Action Surfacing
    # ------------------------------------------------------------------
    def get_actions(self, strategy_path) -> list[RepresentativeAction]:
        """Load representative actions for the selected strategy path."""
        action_keys = set(strategy_path.representative_actions)
        return [
            a
            for a in self.schema.representative_actions
            if a.action_key in action_keys
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_signals(self, signal_keys: list[str]) -> list[Signal]:
        """Resolve signal keys to Signal objects."""
        result = []
        for key in signal_keys:
            sig = self.schema.get_signal(key)
            if sig is not None:
                result.append(sig)
        return result

    @staticmethod
    def _looks_like_signal_key(s: str) -> bool:
        """Return True if a string looks like a signal key (short, snake_case, no spaces)."""
        t = s.strip()
        return " " not in t and "_" in t and len(t) < 60

    # ------------------------------------------------------------------
    # 1.8: Signal-to-Lever Mapping Traceability
    # ------------------------------------------------------------------
    def build_signal_lever_map(self, signal_keys: list[str]) -> dict[str, list[str]]:
        """Return a mapping of signal_key -> affected_levers for the given signals."""
        result: dict[str, list[str]] = {}
        for key in signal_keys:
            sig = self.schema.get_signal(key)
            if sig is not None:
                result[key] = list(sig.affected_levers)
        return result

    # ------------------------------------------------------------------
    # 1.10: Evaluation Transparency Summary
    # ------------------------------------------------------------------
    def generate_transparency_summary(self, result: DecisionResult) -> str:
        """Generate a human-readable summary explaining why patterns were
        activated and which strategy was selected."""
        lines: list[str] = []

        if not result.primary_pattern:
            lines.append("No patterns were activated — no active signals met "
                         "the threshold for pattern activation.")
            return " ".join(lines)

        # Explain active signals
        sig_names = []
        for key in result.active_signals:
            sig = self.schema.get_signal(key)
            sig_names.append(sig.name if sig else key)
        lines.append(f"Active signals: {', '.join(sig_names)}.")

        # Explain primary pattern
        pat = self.schema.get_pattern(result.primary_pattern)
        pat_name = pat.name if pat else result.primary_pattern
        lines.append(f"Primary pattern activated: {result.primary_pattern} "
                      f"({pat_name}).")

        # Explain which signals triggered the primary pattern
        if pat:
            triggering = [k for k in result.active_signals
                          if self.schema.get_signal(k) and
                          result.primary_pattern in self.schema.get_signal(k).target_patterns]
            if triggering:
                lines.append(f"Triggered by: {', '.join(triggering)}.")

        # Strategy path
        if result.strategy_path:
            sp = self.schema.get_strategy_path(result.strategy_path)
            sp_name = sp.display_name if sp else result.strategy_path
            lines.append(f"Selected strategy: {result.strategy_path} ({sp_name}).")

        # Lever states
        weak_levers = [k for k, v in result.lever_states.items() if v == "WEAK"]
        if weak_levers:
            lines.append(f"Weak levers: {', '.join(weak_levers)}.")

        return " ".join(lines)

    # ------------------------------------------------------------------
    # 1.13: Full Lever Coverage Check
    # ------------------------------------------------------------------
    def check_lever_coverage(
        self, signal_keys: list[str] | None = None
    ) -> dict:
        """Verify all levers have at least one signal covering them.

        If signal_keys is None, checks against the full schema signal set.
        Returns {"covered": bool, "uncovered_levers": [...], "coverage_map": {...}}.
        """
        signals: list[Signal]
        if signal_keys is not None:
            signals = [s for s in self.schema.signals if s.key in set(signal_keys)]
        else:
            signals = list(self.schema.signals)

        coverage_map: dict[str, list[str]] = {lk: [] for lk in LEVER_ORDER}
        for sig in signals:
            for lever in sig.affected_levers:
                if lever in coverage_map:
                    coverage_map[lever].append(sig.key)

        uncovered = [lk for lk, sigs in coverage_map.items() if not sigs]
        return {
            "covered": len(uncovered) == 0,
            "uncovered_levers": uncovered,
            "coverage_map": coverage_map,
        }

    # ------------------------------------------------------------------
    # 1.14: Pattern Activation Trace
    # ------------------------------------------------------------------
    def build_pattern_activation_trace(
        self, signal_keys: list[str]
    ) -> dict[str, list[str]]:
        """Return a mapping of pattern_key -> [signal_keys that triggered it]."""
        signals = self._resolve_signals(signal_keys)
        trace: dict[str, list[str]] = {}
        for sig in signals:
            for pk in sig.target_patterns:
                if self.schema.get_pattern(pk) is not None:
                    trace.setdefault(pk, []).append(sig.key)
        return trace


# ═══════════════════════════════════════════════════════════════════════════
# 1.17: Session History Diffing — compare two evaluation snapshots
# ═══════════════════════════════════════════════════════════════════════════
def diff_snapshots(snap_a: dict, snap_b: dict) -> dict:
    """Compare two evaluation snapshots and return a structured diff."""
    a_signals = set(snap_a.get("active_signals", []))
    b_signals = set(snap_b.get("active_signals", []))

    a_levers = snap_a.get("lever_states", {})
    b_levers = snap_b.get("lever_states", {})
    lever_changes: dict[str, dict[str, str]] = {}
    all_lever_keys = set(a_levers) | set(b_levers)
    for lk in all_lever_keys:
        before = a_levers.get(lk)
        after = b_levers.get(lk)
        if before != after:
            lever_changes[lk] = {"before": before, "after": after}

    a_primary = snap_a.get("primary_pattern")
    b_primary = snap_b.get("primary_pattern")

    a_strategy = snap_a.get("strategy_path")
    b_strategy = snap_b.get("strategy_path")

    return {
        "signals_added": sorted(b_signals - a_signals),
        "signals_removed": sorted(a_signals - b_signals),
        "lever_changes": lever_changes,
        "primary_pattern_changed": a_primary != b_primary,
        "primary_pattern": {"before": a_primary, "after": b_primary}
        if a_primary != b_primary else None,
        "strategy_path_changed": a_strategy != b_strategy,
        "strategy_path": {"before": a_strategy, "after": b_strategy}
        if a_strategy != b_strategy else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1.19: Monitoring Trigger Conditions — re-evaluation logic
# ═══════════════════════════════════════════════════════════════════════════
def should_trigger_re_evaluation(
    strategy_path: StrategyPath,
    new_signals: list[str],
    progress_status: str = "neutral",
) -> dict:
    """Determine if re-evaluation should be triggered during monitoring.

    Args:
        strategy_path: The active strategy path.
        new_signals: Newly detected signal keys.
        progress_status: "positive", "negative", or "neutral".

    Returns:
        {"should_re_evaluate": bool, "reasons": [str]}
    """
    reasons: list[str] = []

    # Check transition signals
    transition_set = set(strategy_path.transition_signals)
    if transition_set & set(new_signals):
        reasons.append("transition_signal_match")

    # Check negative progress
    if progress_status == "negative":
        reasons.append("negative_progress")

    return {
        "should_re_evaluate": len(reasons) > 0,
        "reasons": reasons,
    }
