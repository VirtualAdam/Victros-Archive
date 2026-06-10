"""Tier SV — Signal Validation Tests (SV-01 → SV-08).

Tests for the validate_signals function that will be added to
server.decision_engine. This function checks structural preconditions,
confidence thresholds, and evidence requirements before activating signals.

All tests are marked xfail because validate_signals does not exist yet.
These define the expected contract for Phase 1 implementation.
"""
from __future__ import annotations

import pathlib

import pytest

from server.models import ActiveSignal

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


@pytest.fixture
def schema_store():
    from server.schema_store import SchemaStore

    return SchemaStore(SCHEMA_DIR)


def _make_candidate(
    key: str,
    confidence: float = 0.8,
    evidence_text: str | None = None,
    source: str = "system",
) -> dict:
    """Helper to build a candidate signal dict."""
    return {
        "key": key,
        "confidence": confidence,
        "evidence_text": evidence_text,
        "source": source,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Structural Precondition Validation (SRS 1.5)
# ═══════════════════════════════════════════════════════════════════════════


class TestStructuralPreconditions:
    """SV-01 / SV-02: trigger_input_conditions checked against intake fields."""

    def test_sv01_validate_rejects_signal_failing_preconditions(self, schema_store):
        """A signal whose trigger_input_conditions reference fields NOT present
        in intake_fields should be rejected (not appear in output)."""
        from server.decision_engine import validate_signals

        # single_threaded_contact requires "Stakeholder Coverage = Single stakeholder"
        candidates = [_make_candidate("single_threaded_contact", confidence=0.9)]

        # Intake fields that do NOT satisfy the precondition
        intake_fields = {
            "deal_stage": "3_Validation",
            "offering_type": "product",
            # No stakeholder_coverage field at all
        }

        result = validate_signals(candidates, intake_fields, schema_store)

        # Signal should be filtered out — precondition not met
        activated_keys = [s.key for s in result]
        assert "single_threaded_contact" not in activated_keys

    def test_sv02_validate_passes_signal_meeting_preconditions(self, schema_store):
        """A signal whose trigger_input_conditions ARE satisfied should pass."""
        from server.decision_engine import validate_signals

        candidates = [_make_candidate("single_threaded_contact", confidence=0.9)]

        # Intake fields that DO satisfy "Stakeholder Coverage = Single stakeholder"
        intake_fields = {
            "deal_stage": "3_Validation",
            "stakeholder_coverage": "Single stakeholder",
        }

        result = validate_signals(candidates, intake_fields, schema_store)

        activated_keys = [s.key for s in result]
        assert "single_threaded_contact" in activated_keys


# ═══════════════════════════════════════════════════════════════════════════
# Confidence Threshold Filtering (SRS 1.2)
# ═══════════════════════════════════════════════════════════════════════════


class TestConfidenceThreshold:
    """SV-03 / SV-04: Signals below confidence_threshold are excluded."""

    def test_sv03_confidence_below_threshold_flagged(self, schema_store):
        """A signal with confidence below its threshold should not activate."""
        from server.decision_engine import validate_signals

        # Use a signal that exists in schema; set confidence very low
        candidates = [_make_candidate("champion_coaching_influence", confidence=0.1)]

        # Provide intake fields that would otherwise satisfy preconditions
        intake_fields = {
            "deal_stage": "3_Validation",
            "champion_status": "active advocacy",
            "recent_interaction_summary": "stakeholder introductions",
        }

        # Temporarily patch the signal's confidence_threshold to 0.5 for test
        signal = schema_store.get_signal("champion_coaching_influence")
        original_threshold = signal.confidence_threshold
        signal.confidence_threshold = 0.5
        try:
            result = validate_signals(candidates, intake_fields, schema_store)
            activated_keys = [s.key for s in result]
            assert "champion_coaching_influence" not in activated_keys
        finally:
            signal.confidence_threshold = original_threshold

    def test_sv04_confidence_above_threshold_activated(self, schema_store):
        """A signal with confidence above threshold should activate."""
        from server.decision_engine import validate_signals

        candidates = [_make_candidate("champion_coaching_influence", confidence=0.8)]

        intake_fields = {
            "deal_stage": "3_Validation",
            "champion_status": "active advocacy",
            "recent_interaction_summary": "stakeholder introductions",
        }

        signal = schema_store.get_signal("champion_coaching_influence")
        original_threshold = signal.confidence_threshold
        signal.confidence_threshold = 0.5
        try:
            result = validate_signals(candidates, intake_fields, schema_store)
            activated_keys = [s.key for s in result]
            assert "champion_coaching_influence" in activated_keys
        finally:
            signal.confidence_threshold = original_threshold


# ═══════════════════════════════════════════════════════════════════════════
# Evidence Requirements (SRS 1.8)
# ═══════════════════════════════════════════════════════════════════════════


class TestEvidenceRequirements:
    """SV-05 / SV-06 / SV-07: Critical signals require evidence_text."""

    def test_sv05_critical_signal_without_evidence_blocked(self, schema_store):
        """A CRITICAL signal with requires_evidence=True and no evidence_text
        should NOT activate."""
        from server.decision_engine import validate_signals

        # problem_not_validated is CRITICAL severity
        candidates = [
            _make_candidate("problem_not_validated", confidence=0.9, evidence_text=None),
        ]

        intake_fields = {
            "deal_stage": "3_Validation",
            "pain": "Budget pressure from board",
            # measurable_impact intentionally absent → trigger matches
        }

        signal = schema_store.get_signal("problem_not_validated")
        original_flag = signal.requires_evidence
        signal.requires_evidence = True
        try:
            result = validate_signals(candidates, intake_fields, schema_store)
            activated_keys = [s.key for s in result]
            assert "problem_not_validated" not in activated_keys
        finally:
            signal.requires_evidence = original_flag

    def test_sv06_critical_signal_with_evidence_activated(self, schema_store):
        """A CRITICAL signal WITH evidence_text should activate normally."""
        from server.decision_engine import validate_signals

        candidates = [
            _make_candidate(
                "problem_not_validated",
                confidence=0.9,
                evidence_text="Client stated no measurable ROI has been established",
            ),
        ]

        intake_fields = {
            "deal_stage": "3_Validation",
            "pain": "Budget pressure from board",
        }

        signal = schema_store.get_signal("problem_not_validated")
        original_flag = signal.requires_evidence
        signal.requires_evidence = True
        try:
            result = validate_signals(candidates, intake_fields, schema_store)
            activated_keys = [s.key for s in result]
            assert "problem_not_validated" in activated_keys
            # Verify evidence is preserved on the ActiveSignal
            active = next(s for s in result if s.key == "problem_not_validated")
            assert active.evidence_text is not None
        finally:
            signal.requires_evidence = original_flag

    def test_sv07_noncritical_signal_without_evidence_proceeds(self, schema_store):
        """A non-critical signal without evidence should still activate
        (evidence is only required when requires_evidence=True)."""
        from server.decision_engine import validate_signals

        # slowdowns_or_silence is MEDIUM severity, requires_evidence defaults to False
        candidates = [
            _make_candidate("slowdowns_or_silence", confidence=0.7, evidence_text=None),
        ]

        intake_fields = {
            "deal_stage": "3_Validation",
            "recent_interaction_summary": "delayed responses, no next step",
        }

        result = validate_signals(candidates, intake_fields, schema_store)
        activated_keys = [s.key for s in result]
        assert "slowdowns_or_silence" in activated_keys


# ═══════════════════════════════════════════════════════════════════════════
# ActiveSignal Shape (SRS 1.6)
# ═══════════════════════════════════════════════════════════════════════════


class TestActiveSignalShape:
    """SV-08: validate_signals returns ActiveSignal instances."""

    def test_sv08_active_signal_shape(self, schema_store):
        """Each element in the result must be an ActiveSignal with the correct fields."""
        from server.decision_engine import validate_signals

        candidates = [
            _make_candidate(
                "economic_buyer_engagement",
                confidence=0.85,
                evidence_text="EB met in last call",
                source="system",
            ),
        ]

        intake_fields = {
            "deal_stage": "3_Validation",
            "economic_buyer_identified": "Yes",
            "economic_buyer_engagement": "Direct",
        }

        result = validate_signals(candidates, intake_fields, schema_store)
        assert len(result) >= 1

        sig = result[0]
        assert isinstance(sig, ActiveSignal)
        assert sig.key == "economic_buyer_engagement"
        assert sig.confidence == 0.85
        assert sig.evidence_text == "EB met in last call"
        assert sig.source == "system"
