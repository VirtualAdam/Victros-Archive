"""Tier 1 — Schema Store Tests (S-01 → S-12).

Tests for the schema loading and cross-reference validation.
Written BEFORE schema_store.py exists.
"""
import json
import pathlib
import tempfile

import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


# ---------------------------------------------------------------------------
# S-01: Load signals.json → 18 Signal models
# ---------------------------------------------------------------------------
class TestSchemaStoreLoad:
    def test_s01_load_signals(self):
        from server.schema_store import SchemaStore

        store = SchemaStore(SCHEMA_DIR)
        assert len(store.signals) == 23

    # -----------------------------------------------------------------------
    # S-02: Load patterns.json → 20 Pattern models
    # -----------------------------------------------------------------------
    def test_s02_load_patterns(self):
        from server.schema_store import SchemaStore

        store = SchemaStore(SCHEMA_DIR)
        assert len(store.patterns) == 22

    # -----------------------------------------------------------------------
    # S-03: Load strategy_paths.json → 12 StrategyPath models
    # -----------------------------------------------------------------------
    def test_s03_load_strategy_paths(self):
        from server.schema_store import SchemaStore

        store = SchemaStore(SCHEMA_DIR)
        assert len(store.strategy_paths) == 13

    # -----------------------------------------------------------------------
    # S-04: Load levers.json → 7 Lever models
    # -----------------------------------------------------------------------
    def test_s04_load_levers(self):
        from server.schema_store import SchemaStore

        store = SchemaStore(SCHEMA_DIR)
        assert len(store.levers) == 7

    # -----------------------------------------------------------------------
    # S-05: Load sales_zones.json → 4 SalesZone models
    # -----------------------------------------------------------------------
    def test_s05_load_sales_zones(self):
        from server.schema_store import SchemaStore

        store = SchemaStore(SCHEMA_DIR)
        assert len(store.sales_zones) == 4

    # -----------------------------------------------------------------------
    # S-06: Load representative_actions.json → all reference valid strategy
    #       path keys
    # -----------------------------------------------------------------------
    def test_s06_load_representative_actions(self):
        from server.schema_store import SchemaStore

        store = SchemaStore(SCHEMA_DIR)
        assert len(store.representative_actions) > 0
        sp_keys = {sp.key for sp in store.strategy_paths}
        for action in store.representative_actions:
            assert action.parent_strategy_path in sp_keys, (
                f"Action {action.action_key} references unknown strategy path "
                f"'{action.parent_strategy_path}'"
            )


# ---------------------------------------------------------------------------
# Cross-reference integrity
# ---------------------------------------------------------------------------
class TestSchemaStoreCrossReferences:
    @pytest.fixture(autouse=True)
    def _load_store(self):
        from server.schema_store import SchemaStore

        self.store = SchemaStore(SCHEMA_DIR)

    # S-07: All pattern trigger_signals reference valid signal keys
    def test_s07_pattern_trigger_signals_valid(self):
        signal_keys = {s.key for s in self.store.signals}
        for pattern in self.store.patterns:
            for trigger in pattern.trigger_signals:
                assert trigger in signal_keys, (
                    f"Pattern '{pattern.key}' trigger_signal '{trigger}' "
                    f"not found in signals"
                )

    # S-08: All pattern candidate_strategy_path_keys reference valid
    #       strategy path keys
    def test_s08_pattern_strategy_path_keys_valid(self):
        sp_keys = {sp.key for sp in self.store.strategy_paths}
        for pattern in self.store.patterns:
            for spk in pattern.candidate_strategy_path_keys:
                assert spk in sp_keys, (
                    f"Pattern '{pattern.key}' candidate_strategy_path_key "
                    f"'{spk}' not found in strategy_paths"
                )

    # S-09: All strategy path representative_actions exist in
    #       representative_actions.json
    def test_s09_strategy_path_actions_valid(self):
        action_keys = {a.action_key for a in self.store.representative_actions}
        for sp in self.store.strategy_paths:
            for ak in sp.representative_actions:
                assert ak in action_keys, (
                    f"StrategyPath '{sp.key}' representative_action '{ak}' "
                    f"not found in representative_actions"
                )

    # S-11: All signal affected_levers reference valid lever names
    def test_s11_signal_affected_levers_valid(self):
        lever_keys = {l.key for l in self.store.levers}
        for signal in self.store.signals:
            for lk in signal.affected_levers:
                assert lk in lever_keys, (
                    f"Signal '{signal.key}' affected_lever '{lk}' "
                    f"not found in levers"
                )

    # S-12: All strategy path target_levers reference valid lever names
    def test_s12_strategy_path_target_levers_valid(self):
        lever_keys = {l.key for l in self.store.levers}
        for sp in self.store.strategy_paths:
            for lk in sp.target_levers:
                assert lk in lever_keys, (
                    f"StrategyPath '{sp.key}' target_lever '{lk}' "
                    f"not found in levers"
                )


# ---------------------------------------------------------------------------
# S-10: Malformed JSON raises clear error
# ---------------------------------------------------------------------------
class TestSchemaStoreErrors:
    def test_s10_malformed_json(self):
        from server.schema_store import SchemaStore, SchemaLoadError

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            # Write valid files except signals which is broken
            for name in [
                "levers.json",
                "sales_zones.json",
                "patterns.json",
                "strategy_paths.json",
                "representative_actions.json",
            ]:
                src = SCHEMA_DIR / name
                (tmp / name).write_text(src.read_text())

            # Write a malformed signals.json
            (tmp / "signals.json").write_text("{this is not valid json")

            with pytest.raises(SchemaLoadError) as exc_info:
                SchemaStore(tmp)
            assert "signals.json" in str(exc_info.value)
