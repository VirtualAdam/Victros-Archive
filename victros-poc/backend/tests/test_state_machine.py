"""Tier 1 — State Machine Transition Tests (ST-01 → ST-21).

Written BEFORE state_machine.py exists.
Tests valid and invalid state transitions.
"""
import pytest


class TestValidTransitions:
    # ST-01: NEW_SESSION → INTENT_CAPTURE
    def test_st01_new_session_to_intent_capture(self):
        from server.state_machine import validate_transition

        assert validate_transition("NEW_SESSION", "INTENT_CAPTURE") is True

    # ST-02: INTAKE → AWAITING_CONFIRMATION
    def test_st02_intake_to_awaiting(self):
        from server.state_machine import validate_transition

        assert validate_transition("INTAKE", "AWAITING_CONFIRMATION") is True

    # ST-03: AWAITING_CONFIRMATION → EVALUATING
    def test_st03_awaiting_to_evaluating(self):
        from server.state_machine import validate_transition

        assert validate_transition("AWAITING_CONFIRMATION", "EVALUATING") is True

    # ST-04: AWAITING_CONFIRMATION → INTAKE (not ready)
    def test_st04_awaiting_to_intake(self):
        from server.state_machine import validate_transition

        assert validate_transition("AWAITING_CONFIRMATION", "INTAKE") is True

    # ST-05: AWAITING_CONFIRMATION → INTAKE (rejected)
    def test_st05_awaiting_rejected(self):
        from server.state_machine import validate_transition

        assert validate_transition("AWAITING_CONFIRMATION", "INTAKE") is True

    # ST-06: EVALUATING → PATTERN_DIAGNOSTICS (not PRESENTING_DIAGNOSIS directly)
    # The engine activates patterns and the user must confirm them before
    # a strategy path is selected. PRESENTING_DIAGNOSIS comes after that.
    def test_st06_evaluating_to_pattern_diagnostics(self):
        from server.state_machine import validate_transition

        assert validate_transition("EVALUATING", "PATTERN_DIAGNOSTICS") is True

    # ST-06b: PATTERN_DIAGNOSTICS → PRESENTING_DIAGNOSIS
    def test_st06b_pattern_diagnostics_to_presenting(self):
        from server.state_machine import validate_transition

        assert validate_transition("PATTERN_DIAGNOSTICS", "PRESENTING_DIAGNOSIS") is True

    # ST-07: PRESENTING_DIAGNOSIS → ACTION_SELECTION (now invalid — must go through ALIGNMENT_CHECKPOINT)
    def test_st07_presenting_to_action(self):
        from server.state_machine import validate_transition

        assert validate_transition("PRESENTING_DIAGNOSIS", "ACTION_SELECTION") is False

    # ST-08: PRESENTING_DIAGNOSIS → DUAL_PATTERN_TRADEOFF (now invalid — must go through ALIGNMENT_CHECKPOINT)
    def test_st08_presenting_to_dual(self):
        from server.state_machine import validate_transition

        assert validate_transition("PRESENTING_DIAGNOSIS", "DUAL_PATTERN_TRADEOFF") is False

    # ST-09: INTENT_CAPTURE → SITUATION_VALIDATION
    def test_st09_intent_capture_to_situation_validation(self):
        from server.state_machine import validate_transition

        assert validate_transition("INTENT_CAPTURE", "SITUATION_VALIDATION") is True

    # ST-10: DUAL_PATTERN_TRADEOFF → ACTION_SELECTION
    def test_st10_dual_to_action(self):
        from server.state_machine import validate_transition

        assert validate_transition("DUAL_PATTERN_TRADEOFF", "ACTION_SELECTION") is True

    # ST-11: ACTION_SELECTION → MONITORING
    def test_st11_action_to_monitoring(self):
        from server.state_machine import validate_transition

        assert validate_transition("ACTION_SELECTION", "MONITORING") is True

    # ST-12: MONITORING → RE_EVALUATING
    def test_st12_monitoring_to_reevaluating(self):
        from server.state_machine import validate_transition

        assert validate_transition("MONITORING", "RE_EVALUATING") is True

    # ST-13: RE_EVALUATING → MONITORING
    def test_st13_reevaluating_to_monitoring(self):
        from server.state_machine import validate_transition

        assert validate_transition("RE_EVALUATING", "MONITORING") is True

    # ST-14: RE_EVALUATING → PRESENTING_DIAGNOSIS
    def test_st14_reevaluating_to_presenting(self):
        from server.state_machine import validate_transition

        assert validate_transition("RE_EVALUATING", "PRESENTING_DIAGNOSIS") is True

    # ST-15: RE_EVALUATING → SESSION_COMPLETE
    def test_st15_reevaluating_to_complete(self):
        from server.state_machine import validate_transition

        assert validate_transition("RE_EVALUATING", "SESSION_COMPLETE") is True

    # ST-16: SITUATION_VALIDATION → INTAKE
    def test_st16_situation_validation_to_intake(self):
        from server.state_machine import validate_transition

        assert validate_transition("SITUATION_VALIDATION", "INTAKE") is True

    # ST-17: SITUATION_VALIDATION → INTENT_CAPTURE (correction)
    def test_st17_situation_validation_to_intent_capture(self):
        from server.state_machine import validate_transition

        assert validate_transition("SITUATION_VALIDATION", "INTENT_CAPTURE") is True

    # ST-18: SESSION_COMPLETE → INTENT_CAPTURE
    def test_st18_complete_to_intent_capture(self):
        from server.state_machine import validate_transition

        assert validate_transition("SESSION_COMPLETE", "INTENT_CAPTURE") is True

    # ST-23: PRESENTING_DIAGNOSIS → ALIGNMENT_CHECKPOINT (Phase 4)
    def test_st23_presenting_to_alignment_checkpoint(self):
        from server.state_machine import validate_transition

        assert validate_transition("PRESENTING_DIAGNOSIS", "ALIGNMENT_CHECKPOINT") is True

    # ST-24: ALIGNMENT_CHECKPOINT → ACTION_SELECTION (Phase 4)
    def test_st24_alignment_checkpoint_to_action_selection(self):
        from server.state_machine import validate_transition

        assert validate_transition("ALIGNMENT_CHECKPOINT", "ACTION_SELECTION") is True

    # ST-25: ALIGNMENT_CHECKPOINT → INTAKE (Phase 4 — does_not_match)
    def test_st25_alignment_checkpoint_to_intake(self):
        from server.state_machine import validate_transition

        assert validate_transition("ALIGNMENT_CHECKPOINT", "INTAKE") is True

    # ST-26: MONITORING → SESSION_PAUSED (Phase 5 — exit_for_now)
    def test_st26_monitoring_to_session_paused(self):
        from server.state_machine import validate_transition

        assert validate_transition("MONITORING", "SESSION_PAUSED") is True


class TestInvalidTransitions:
    # ST-19: NEW_SESSION → EVALUATING (invalid)
    def test_st19_invalid_new_to_evaluating(self):
        from server.state_machine import validate_transition

        assert validate_transition("NEW_SESSION", "EVALUATING") is False

    # ST-20: MONITORING → SESSION_COMPLETE is now valid
    def test_st20_monitoring_to_complete(self):
        from server.state_machine import validate_transition

        assert validate_transition("MONITORING", "SESSION_COMPLETE") is True

    # ST-21: INTAKE → PRESENTING_DIAGNOSIS (invalid)
    def test_st21_invalid_intake_to_presenting(self):
        from server.state_machine import validate_transition

        assert validate_transition("INTAKE", "PRESENTING_DIAGNOSIS") is False

    # ST-22: EVALUATING → PRESENTING_DIAGNOSIS (invalid — must go through PATTERN_DIAGNOSTICS)
    def test_st22_invalid_evaluating_to_presenting(self):
        from server.state_machine import validate_transition

        assert validate_transition("EVALUATING", "PRESENTING_DIAGNOSIS") is False

    # ST-27: PRESENTING_DIAGNOSIS → ACTION_SELECTION is NOW invalid (Phase 4 — must go through checkpoint)
    def test_st27_invalid_presenting_direct_to_action(self):
        from server.state_machine import validate_transition

        assert validate_transition("PRESENTING_DIAGNOSIS", "ACTION_SELECTION") is False
