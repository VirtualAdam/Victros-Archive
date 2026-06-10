"""Loads and validates the SRS schema JSON files.

Loaded once at startup, immutable at runtime.
"""
from __future__ import annotations

import json
import pathlib

from server.models import (
    Lever,
    Pattern,
    RepresentativeAction,
    SalesZone,
    Signal,
    StrategyPath,
)


class SchemaLoadError(Exception):
    """Raised when a schema JSON file cannot be loaded or parsed."""


class SchemaStore:
    """Immutable container for the full SRS schema."""

    def __init__(self, schema_dir: pathlib.Path) -> None:
        self.signals = self._load(schema_dir / "signals.json", Signal)
        self.patterns = self._load(schema_dir / "patterns.json", Pattern)
        self.strategy_paths = self._load(
            schema_dir / "strategy_paths.json", StrategyPath
        )
        self.levers = self._load(schema_dir / "levers.json", Lever)
        self.sales_zones = self._load(schema_dir / "sales_zones.json", SalesZone)
        self.representative_actions = self._load(
            schema_dir / "representative_actions.json", RepresentativeAction
        )

    # -- Lookup helpers ---------------------------------------------------
    def get_signal(self, key: str) -> Signal | None:
        return self._by_key(self.signals, key)

    def get_pattern(self, key: str) -> Pattern | None:
        return self._by_key(self.patterns, key)

    def get_strategy_path(self, key: str) -> StrategyPath | None:
        return self._by_key(self.strategy_paths, key)

    def get_lever(self, key: str) -> Lever | None:
        return self._by_key(self.levers, key)

    def get_representative_action(self, key: str) -> RepresentativeAction | None:
        return self._by_key(self.representative_actions, key)

    def get_patterns_by_keys(self, keys: list[str]) -> list[Pattern]:
        """Return Pattern objects for the given keys, preserving order."""
        return [p for p in self.patterns if p.key in keys]

    # -- Sorted accessors ------------------------------------------------
    _SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    _POLARITY_RANK = {"negative": 0, "positive": 1}  # risks before strengths

    def signals_sorted(self) -> list:
        """Return signals sorted CRITICAL→LOW, negative before positive within tier."""
        return sorted(
            self.signals,
            key=lambda s: (
                self._SEVERITY_RANK.get(s.severity, 9),
                self._POLARITY_RANK.get(s.polarity, 9),
            ),
        )

    def get_zone_for_stage(self, stage: str) -> SalesZone | None:
        """Map a deal stage string to a SalesZone.

        Accepts zone keys directly (zone1–zone4) or numeric prefixes (1–4).
        Falls back to zone2 if unrecognised.
        """
        if not stage:
            return None
        s = stage.strip().lower()
        # Direct key match (zone1, zone2, ...)
        for zone in self.sales_zones:
            if zone.key == s:
                return zone
        # Numeric prefix match: "1_...", "2_...", "1", "2" etc.
        for zone in self.sales_zones:
            suffix = zone.key.replace("zone", "")  # "1", "2", ...
            if s.startswith(suffix + "_") or s == suffix:
                return zone
        # Stage name keyword heuristic
        lower_stage = s.lower()
        if any(w in lower_stage for w in ("discovery", "pre-qual", "prequal", "early")):
            return self._by_key(self.sales_zones, "zone1")
        if any(w in lower_stage for w in ("evaluation", "qualification")):
            return self._by_key(self.sales_zones, "zone2")
        if any(w in lower_stage for w in ("validation", "consensus", "mid")):
            return self._by_key(self.sales_zones, "zone3")
        if any(w in lower_stage for w in ("negotiat", "clos", "late")):
            return self._by_key(self.sales_zones, "zone4")
        return None

    # -- Internal ---------------------------------------------------------
    @staticmethod
    def _load(path: pathlib.Path, model_cls: type) -> list:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SchemaLoadError(
                f"Failed to parse {path.name}: {exc}"
            ) from exc
        except FileNotFoundError as exc:
            raise SchemaLoadError(
                f"Schema file not found: {path.name}"
            ) from exc
        return [model_cls(**item) for item in raw]

    @staticmethod
    def _by_key(items: list, key: str):
        for item in items:
            if getattr(item, "key", getattr(item, "action_key", None)) == key:
                return item
        return None
