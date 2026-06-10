"""Tier 1 — Readiness Check Tests (RC-01 → RC-05).

Updated for the new 6-required-field intake model from data-flow-logic.md.
"""
import pytest


class TestReadinessCheck:
    # RC-01: All 6 required fields present + signals confirmed → ready
    def test_rc01_ready(self):
        from server.readiness_check import check_readiness
        from server.models import IntakeReadiness

        readiness = IntakeReadiness(
            deal_stage="present",
            offering_type="present",
            offering_usage="present",
            usage_depth="present",
            deal_amount="present",
            deal_close_date="present",
            signals_confirmed=True,
        )
        result = check_readiness(readiness)
        assert result["ready"] is True
        assert result["missing"] == []

    # RC-02: Stage missing, signals present → not ready
    def test_rc02_stage_missing(self):
        from server.readiness_check import check_readiness
        from server.models import IntakeReadiness

        readiness = IntakeReadiness(
            deal_stage="missing",
            offering_type="present",
            offering_usage="present",
            usage_depth="present",
            deal_amount="present",
            deal_close_date="present",
            signals_confirmed=True,
        )
        result = check_readiness(readiness)
        assert result["ready"] is False
        assert "deal_stage" in result["missing"]

    # RC-03: All fields present, no signals → not ready
    def test_rc03_signals_missing(self):
        from server.readiness_check import check_readiness
        from server.models import IntakeReadiness

        readiness = IntakeReadiness(
            deal_stage="present",
            offering_type="present",
            offering_usage="present",
            usage_depth="present",
            deal_amount="present",
            deal_close_date="present",
            signals_confirmed=False,
        )
        result = check_readiness(readiness)
        assert result["ready"] is False
        assert "signals" in result["missing"]

    # RC-04: Default (all missing) → not ready
    def test_rc04_both_missing(self):
        from server.readiness_check import check_readiness
        from server.models import IntakeReadiness

        readiness = IntakeReadiness()
        result = check_readiness(readiness)
        assert result["ready"] is False
        assert "deal_stage" in result["missing"]
        assert "signals" in result["missing"]

    # RC-05: deal_notes missing but all required + signals present → ready
    def test_rc05_optional_missing(self):
        from server.readiness_check import check_readiness
        from server.models import IntakeReadiness

        readiness = IntakeReadiness(
            deal_stage="present",
            offering_type="present",
            offering_usage="present",
            usage_depth="present",
            deal_amount="present",
            deal_close_date="present",
            deal_notes="missing",
            signals_confirmed=True,
        )
        result = check_readiness(readiness)
        assert result["ready"] is True
