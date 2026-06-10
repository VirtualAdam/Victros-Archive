"""FastAPI application — endpoint definitions for the Victros POC.

Implements the state machine from data-flow-logic.md:
  S1 NEW_SESSION → S2 INTENT_CAPTURE → S3 SITUATION_VALIDATION →
  S4 INTAKE → S5 AWAITING_CONFIRMATION → S6 EVALUATING →
  S7 PATTERN_DIAGNOSTICS → S8 PRESENTING_DIAGNOSIS →
  S9 DUAL_PATTERN_TRADEOFF → S10 ACTION_SELECTION → S11 MONITORING
"""
from __future__ import annotations

import os
import pathlib
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.auth import SNAPSHOT_ADMIN_ROLE, get_caller_user_id, has_role, is_authenticated
from server.confirmation_gate import ConfirmationGate
from server.db.base import SessionRepository
from server.decision_engine import DecisionEngine
from server.llm.client import set_session_context
from server.llm.extraction_service import extract
from server.llm.explanation_service import explain
from server.llm.general_assist import assist
from server.llm.intent_router import classify
from server.models import ActivePatterns, DealSnapshot, DecisionSnapshot, IntakeReadiness
from server.pattern_diagnostics import format_pattern_group, process_pattern_confirmation
from server.progress_evaluator import evaluate_progress
from server.readiness_check import REQUIRED_INTAKE_FIELDS, check_readiness
from server.schema_store import SchemaStore
from server.session_manager import SessionManager
from server.snapshot.renderer import render_markdown
from server.snapshot.renderer_html import render_html
from server.snapshot.service import generate_snapshot
from server.state_machine import validate_transition

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"

# Required intake field prompts (data-flow-logic.md S4) — mandatory order.
INTAKE_FIELD_PROMPTS: dict[str, str] = {
    "deal_stage": "What stage is this deal in?",
    "offering_type": "Is this a product, services, or hybrid deal?",
    "offering_usage": "Is the product already in use at this account?",
    "usage_depth": "How deeply is the product embedded in their workflows?",
    "deal_amount": "What's the deal size?",
    "close_date": "When is the expected close date?",
}


def _next_intake_prompt(readiness: IntakeReadiness) -> dict | None:
    """Return the next required field prompt, or None if all fields collected."""
    for field in REQUIRED_INTAKE_FIELDS:
        # Map close_date field name (readiness uses deal_close_date)
        readiness_field = field
        value = getattr(readiness, readiness_field, "missing")
        if value == "missing":
            prompt_key = "close_date" if field == "deal_close_date" else field
            return {
                "field": field,
                "prompt": INTAKE_FIELD_PROMPTS.get(prompt_key, f"Please provide {field}"),
            }
    return None


def _resolve_actions(schema_store, action_keys: list[str]) -> list[dict]:
    """Resolve action key strings to full action objects for API responses."""
    result = []
    for key in action_keys:
        obj = schema_store.get_representative_action(key)
        if obj:
            result.append({
                "action_key": obj.action_key,
                "description": obj.description,
                "ux_text": obj.ux_text,
            })
        else:
            result.append({"action_key": key, "description": "", "ux_text": ""})
    return result


def _make_snapshot_store(sessions_dir: pathlib.Path | None):
    """Select snapshot storage backend, mirroring _make_repository."""
    backend = os.environ.get("STORAGE_BACKEND", "file").lower()
    if backend == "cosmos":
        conn_str = os.environ.get("COSMOS_CONNECTION_STRING")
        verify_ssl = os.environ.get("COSMOS_VERIFY_SSL", "true").lower() != "false"
        from server.snapshot.store import CosmosSnapshotStore
        return CosmosSnapshotStore(conn_str, verify_ssl=verify_ssl)
    snapshots_dir = (sessions_dir or pathlib.Path("sessions")).parent / "snapshots"
    from server.snapshot.store import FileSnapshotStore
    return FileSnapshotStore(snapshots_dir)


def _make_repository(sessions_dir: pathlib.Path | None) -> SessionRepository:
    """Select session storage backend from STORAGE_BACKEND env var.

    STORAGE_BACKEND=file  (default) — JSON files, no extra services needed.
    STORAGE_BACKEND=cosmos          — Azure Cosmos DB or local emulator.
    """
    backend = os.environ.get("STORAGE_BACKEND", "file").lower()
    if backend == "cosmos":
        conn_str = os.environ.get("COSMOS_CONNECTION_STRING")
        if not conn_str:
            raise RuntimeError(
                "COSMOS_CONNECTION_STRING must be set when STORAGE_BACKEND=cosmos"
            )
        verify_ssl = os.environ.get("COSMOS_VERIFY_SSL", "true").lower() != "false"
        from server.db.cosmos import CosmosSessionRepository
        return CosmosSessionRepository(conn_str, verify_ssl=verify_ssl)
    return SessionManager(sessions_dir or pathlib.Path("sessions"))


def _run_engine_and_store(
    engine: DecisionEngine,
    schema_store: SchemaStore,
    mgr: SessionRepository,
    session_id: str,
    active_signals: list[str],
    deal_stage: str,
    old_lever_states: dict[str, str],
) -> dict:
    """Run the decision engine, store results, return API response dict.

    Used by both the initial AWAITING_CONFIRMATION→EVALUATING flow and
    the RE_EVALUATING flow. Handles the EVALUATING→PATTERN_DIAGNOSTICS
    transition (S6→S7).
    """
    result = engine.run(active_signals=active_signals, deal_stage=deal_stage)

    # If no signals activated → back to INTAKE (spec S6 hard constraint)
    if not result.active_signals or not result.primary_pattern:
        mgr.update_session(session_id, state="INTAKE")
        return {"state": "INTAKE", "message": "Insufficient signal data. Please provide more context."}

    # Record lever state improvements
    _LEVER_ORDER = {"WEAK": 0, "CONNECTED": 1, "COMMITTED": 2, "EXECUTING": 3}
    improvements = [
        {"lever_key": k, "from": old_lever_states.get(k, "WEAK"), "to": v}
        for k, v in result.lever_states.items()
        if _LEVER_ORDER.get(v, 0) > _LEVER_ORDER.get(old_lever_states.get(k, "WEAK"), 0)
    ]
    if improvements:
        from datetime import datetime, timezone as _tz
        mgr.append_history(session_id, {
            "type": "lever_state_change",
            "changes": improvements,
            "timestamp": datetime.now(_tz.utc).isoformat(),
        })

    activated_keys = (
        ([result.primary_pattern] if result.primary_pattern else [])
        + result.secondary_patterns
    )
    mgr.update_session(
        session_id,
        state="PATTERN_DIAGNOSTICS",
        active_patterns=ActivePatterns(
            primary=result.primary_pattern,
            secondary=result.secondary_patterns,
        ),
        selected_strategy_path=result.strategy_path,
        lever_states=result.lever_states,
    )

    # Capture a per-evaluation DecisionSnapshot
    from uuid import uuid4
    from datetime import datetime, timezone as _tz2
    session_obj = mgr.get_session(session_id)
    if session_obj is not None:
        signal_dicts = [
            {"key": k, "confidence": 1.0}
            for k in result.active_signals
        ]
        snap = DecisionSnapshot(
            snapshot_id=str(uuid4()),
            session_id=session_id,
            user_id=session_obj.user_id,
            opportunity_id=session_obj.opportunity_id,
            evaluation_run_id=len(session_obj.decision_snapshots) + 1,
            timestamp=datetime.now(_tz2.utc).isoformat(),
            active_signals=signal_dicts,
            lever_states=result.lever_states,
            primary_pattern=result.primary_pattern,
            secondary_patterns=result.secondary_patterns,
            selected_strategy_path=result.strategy_path,
            selected_action=result.representative_actions[0] if result.representative_actions else None,
            signal_quality_warnings=[],
        )
        mgr.update_session(
            session_id,
            decision_snapshots=session_obj.decision_snapshots + [snap],
        )

    activated_patterns = schema_store.get_patterns_by_keys(activated_keys)
    group = format_pattern_group(activated_patterns)

    return {
        "state": "PATTERN_DIAGNOSTICS",
        "pattern_group": group,
        "lever_states": result.lever_states,
    }


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class CreateSessionRequest(BaseModel):
    user_id: str
    opportunity_id: str


class InputRequest(BaseModel):
    input_type: str  # "button" | "text" | "fields" | "attachment" | "confirm_derived_signals"
    signals: list[str] | None = None
    content: str | None = None
    fields: dict | None = None  # structured field values for input_type="fields"
    accepted_signals: list[str] | None = None  # for confirm_derived_signals
    rejected_signals: list[str] | None = None  # for confirm_derived_signals


class ConfirmRequest(BaseModel):
    response: str  # "confirm" | "adjust" | "reject" | "correct"
    deal_stage: str | None = None


class SelectActionRequest(BaseModel):
    action_key: str


class DualPatternRequest(BaseModel):
    choice: str  # "focus" | "combine" | "sequence"


class GeneralAssistRequest(BaseModel):
    content: str


class ConfirmPatternsRequest(BaseModel):
    response: str  # "confirm_all" | "reject_all" | "confirm_subset"
    confirmed_keys: list[str] | None = None  # required for "confirm_subset"


class ConfirmUnderstandingRequest(BaseModel):
    response: str  # "confirm" | "clarify"


class ProgressUpdateRequest(BaseModel):
    update_text: str


class ResolveReevaluationRequest(BaseModel):
    trigger: str  # "exit" | "transition"


class AlignmentCheckpointRequest(BaseModel):
    response: str  # "aligned" | "does_not_match" | "something_changed" | "new_session"


class MonitoringActionRequest(BaseModel):
    action: str  # "continue" | "re_evaluate" | "address_next_issue" | "exit_for_now"


class SnapshotGenerateRequest(BaseModel):
    week_start: str | None = None   # ISO date string e.g. "2026-04-06"; omit for current week
    week_end: str | None = None     # ISO date string e.g. "2026-04-12"; omit for current week



# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app(sessions_dir: pathlib.Path | None = None) -> FastAPI:
    app = FastAPI(title="Victros POC API")

    # ALLOWED_ORIGINS: comma-separated list of allowed origins.
    # Defaults to localhost dev server when not set.
    _raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
    allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Init shared services
    schema_store = SchemaStore(SCHEMA_DIR)
    engine = DecisionEngine(schema_store)
    mgr = _make_repository(sessions_dir)
    snap_store = _make_snapshot_store(sessions_dir)

    # Store on app state for access in endpoints
    app.state.schema_store = schema_store
    app.state.engine = engine
    app.state.mgr = mgr
    app.state.snap_store = snap_store

    # ------------------------------------------------------------------
    # Health & Version
    # ------------------------------------------------------------------
    @app.get("/health")
    def health():
        from server.version import VERSION
        return {"status": "ok", "version": VERSION, "signals": len(schema_store.signals)}

    @app.get("/api/version")
    def version():
        from server.version import get_version_info
        return get_version_info()

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------
    @app.post("/api/session/create", status_code=201)
    def create_session(req: CreateSessionRequest, request: Request):
        """S1→S2: Create session in NEW_SESSION, auto-advance to INTENT_CAPTURE."""
        user_id = get_caller_user_id(request) or req.user_id
        session = mgr.create_session(user_id, req.opportunity_id)
        # Auto-advance NEW_SESSION → INTENT_CAPTURE (spec S1→S2)
        mgr.update_session(session.session_id, state="INTENT_CAPTURE")
        session.state = "INTENT_CAPTURE"
        resp = session.model_dump()
        resp["prompt"] = "How can I help you win today?"
        return resp

    @app.get("/api/session/{session_id}")
    def get_session(session_id: str):
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        data = session.model_dump()
        # Expose derived signals stored in intake_fields
        candidate_signals = (session.intake_fields or {}).get("candidate_signals")
        if candidate_signals:
            data["derived_signals"] = candidate_signals
            data["candidate_signals"] = candidate_signals
        return data

    @app.get("/api/session/{session_id}/intake-gaps")
    def get_intake_gaps(session_id: str):
        from server.intake_tracker import IntakeTracker
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        tracker = IntakeTracker.from_dict(session.intake_fields)
        return tracker.get_gaps()

    # ------------------------------------------------------------------
    # Input submission
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/input")
    def submit_input(session_id: str, req: InputRequest):
        """Handles input for INTENT_CAPTURE (S2) and INTAKE (S4) states."""
        set_session_context(session_id)
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        # ── S2: INTENT_CAPTURE — capture free-text intent ──────────────
        if session.state == "INTENT_CAPTURE":
            if req.input_type != "text" or not req.content:
                raise HTTPException(
                    status_code=400,
                    detail="INTENT_CAPTURE requires input_type='text' with content",
                )
            intent_text = req.content.strip()
            if not intent_text:
                raise HTTPException(status_code=400, detail="Intent text cannot be empty")

            # Store intent and advance to SITUATION_VALIDATION (S2→S3)
            situation_summary = f"You described your situation as: {intent_text}"
            mgr.update_session(
                session_id,
                state="SITUATION_VALIDATION",
                intent_text=intent_text,
            )
            return {
                "state": "SITUATION_VALIDATION",
                "situation_summary": situation_summary,
                "options": ["confirm", "correct"],
            }

        # ── S4: INTAKE — structured input collection ───────────────────
        if session.state in ("INTAKE", "NEW_SESSION", "MONITORING"):
            # Legacy: auto-advance NEW_SESSION → INTAKE for backward compat
            if session.state == "NEW_SESSION":
                mgr.update_session(session_id, state="INTAKE")
            # Pivot: MONITORING → allow re-entry for "Something Changed"
            if session.state == "MONITORING":
                pass  # Stay in current state until signals → AWAITING_CONFIRMATION

            if req.input_type == "fields" and req.fields:
                from server.intake_tracker import IntakeTracker
                tracker = IntakeTracker.from_dict(session.intake_fields)
                readiness = session.intake_readiness

                # Map the 6 required fields to readiness
                field_to_readiness = {
                    "deal_stage": "deal_stage",
                    "offering_type": "offering_type",
                    "offering_usage": "offering_usage",
                    "usage_depth": "usage_depth",
                    "deal_amount": "deal_amount",
                    "deal_close_date": "deal_close_date",
                    "close_date": "deal_close_date",
                }

                for field_key, value in req.fields.items():
                    tracker.apply_extracted({field_key: value})
                    readiness_key = field_to_readiness.get(field_key)
                    if readiness_key:
                        setattr(readiness, readiness_key, "present")

                # Also update deal_snapshot if deal_stage provided
                if "deal_stage" in req.fields:
                    stage = req.fields["deal_stage"]
                    snap = session.deal_snapshot or DealSnapshot(stage=stage)
                    snap.stage = stage
                    mgr.update_session(session_id, deal_snapshot=snap)

                mgr.update_session(
                    session_id,
                    intake_fields=tracker.to_dict(),
                    intake_readiness=readiness,
                )

                # Check what's next
                next_prompt = _next_intake_prompt(readiness)
                if next_prompt:
                    return {"state": "INTAKE", "next_prompt": next_prompt}

                # All 6 fields collected — auto-extract candidate signals
                from server.decision_engine import validate_signals

                text_parts = [
                    f"{k}: {v}" for k, v in req.fields.items() if v
                ]
                combined_text = " ".join(text_parts)

                known_keys = [s.key for s in schema_store.signals]
                extraction = extract(combined_text, known_keys)
                raw_signals = extraction.get("candidate_signals", [])

                # Build candidate dicts with confidence scores
                candidate_dicts = [
                    {"key": sk, "confidence": 0.7, "evidence_text": None, "source": "system"}
                    for sk in raw_signals if sk in known_keys
                ]

                # Validate keyword-extracted candidates
                validated = validate_signals(candidate_dicts, req.fields, schema_store)

                derived = [
                    {"key": s.key, "confidence": s.confidence, "source": s.source}
                    for s in validated
                ]

                # Zone-based supplementary derivation: add signals matching
                # the deal stage's zone as lower-confidence candidates
                deal_stage_val = req.fields.get("deal_stage", "")
                zone = schema_store.get_zone_for_stage(deal_stage_val)
                derived_keys = {d["key"] for d in derived}
                if zone:
                    for sig in schema_store.signals:
                        if sig.key in derived_keys:
                            continue
                        if zone.key in sig.zone_bias:
                            derived.append({
                                "key": sig.key,
                                "confidence": round(
                                    sig.confidence_threshold + 0.1, 2
                                ),
                                "source": "zone_derived",
                            })

                # Store derived signals on session for later retrieval
                mgr.update_session(
                    session_id,
                    intake_fields={
                        **tracker.to_dict(),
                        "candidate_signals": derived,
                    },
                )

                return {
                    "state": "INTAKE",
                    "next_prompt": None,
                    "message": "All required fields collected. Review derived signals.",
                    "signals_needed": True,
                    "derived_signals": derived,
                }

            elif req.input_type == "button" and req.signals:
                # Signal selection during INTAKE
                readiness = session.intake_readiness
                readiness.signals_confirmed = True
                mgr.update_session(session_id, intake_readiness=readiness)

                # Check if all required fields are present
                next_prompt = _next_intake_prompt(readiness)
                if next_prompt:
                    # Still missing fields — store signals but stay in INTAKE
                    proposal = ConfirmationGate.format_proposal(req.signals, {})
                    mgr.append_history(session_id, {
                        "type": "signal_proposal",
                        "proposed_signals": req.signals,
                    })
                    return {"state": "INTAKE", "next_prompt": next_prompt, "proposal": proposal}

                # All fields + signals → AWAITING_CONFIRMATION (S4→S5)
                proposal = ConfirmationGate.format_proposal(req.signals, {})
                mgr.update_session(session_id, state="AWAITING_CONFIRMATION")
                mgr.append_history(session_id, {
                    "type": "signal_proposal",
                    "proposed_signals": req.signals,
                })
                return {"state": "AWAITING_CONFIRMATION", "proposal": proposal}

            elif req.input_type == "confirm_derived_signals":
                # User confirms/rejects derived signals
                accepted = req.accepted_signals or []
                rejected = req.rejected_signals or []

                # Set accepted signals as active
                mgr.update_session(
                    session_id,
                    active_signals=accepted,
                    state="AWAITING_CONFIRMATION",
                )

                # Store in history for the confirm endpoint
                readiness = session.intake_readiness
                readiness.signals_confirmed = True
                mgr.update_session(session_id, intake_readiness=readiness)
                mgr.append_history(session_id, {
                    "type": "signal_proposal",
                    "proposed_signals": accepted,
                })

                return {"state": "AWAITING_CONFIRMATION"}

            elif req.input_type == "text" and req.content:
                known_keys = [s.key for s in schema_store.signals]
                extraction = extract(req.content, known_keys)
                signals = extraction.get("candidate_signals", [])
                deal_attrs = extraction.get("deal_attributes", {})

                if signals or deal_attrs:
                    proposal = ConfirmationGate.format_proposal(signals, deal_attrs)
                    mgr.update_session(session_id, state="AWAITING_CONFIRMATION")
                    mgr.append_history(session_id, {
                        "type": "extraction_proposal",
                        "proposed_signals": signals,
                        "deal_attributes": deal_attrs,
                    })
                    return {"state": "AWAITING_CONFIRMATION", "proposal": proposal}

                return {"state": "INTAKE", "message": "No signals extracted"}

            return {"state": session.state}

        # Any other state — reject
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit input in state {session.state}",
        )

    # ------------------------------------------------------------------
    # Confirmation (S3: SITUATION_VALIDATION and S5: AWAITING_CONFIRMATION)
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/confirm")
    def confirm(session_id: str, req: ConfirmRequest):
        set_session_context(session_id)
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        # ── S3: SITUATION_VALIDATION ───────────────────────────────────
        if session.state == "SITUATION_VALIDATION":
            if req.response == "correct":
                # Go back to INTENT_CAPTURE for correction (S3→S2)
                mgr.update_session(session_id, state="INTENT_CAPTURE")
                return {
                    "state": "INTENT_CAPTURE",
                    "prompt": "How can I help you win today?",
                    "correction": True,
                }
            if req.response == "confirm":
                # Advance to INTAKE (S3→S4)
                mgr.update_session(session_id, state="INTAKE")
                readiness = session.intake_readiness
                next_prompt = _next_intake_prompt(readiness)
                return {
                    "state": "INTAKE",
                    "next_prompt": next_prompt,
                }
            raise HTTPException(
                status_code=400,
                detail="SITUATION_VALIDATION requires response 'confirm' or 'correct'",
            )

        # ── S5: AWAITING_CONFIRMATION ──────────────────────────────────
        if session.state != "AWAITING_CONFIRMATION":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot confirm in state {session.state}",
            )

        if req.response == "reject":
            # Clear fields and restart intake (S5→S4 reject branch)
            mgr.update_session(
                session_id,
                state="INTAKE",
                intake_readiness=IntakeReadiness(),
                intake_fields={},
                active_signals=[],
            )
            next_prompt = _next_intake_prompt(IntakeReadiness())
            return {"state": "INTAKE", "next_prompt": next_prompt}

        if req.response == "adjust":
            # Back to INTAKE with fields pre-populated (S5→S4 adjust branch)
            mgr.update_session(session_id, state="INTAKE")
            readiness = session.intake_readiness
            next_prompt = _next_intake_prompt(readiness)
            return {"state": "INTAKE", "action": "re_entry", "next_prompt": next_prompt}

        # req.response == "confirm" → S5→S6→S7 (EVALUATING is transient)
        history = session.interaction_history
        proposed_signals: list[str] = []
        for entry in reversed(history):
            if entry.get("type") in ("signal_proposal", "extraction_proposal"):
                proposed_signals = entry.get("proposed_signals", [])
                break

        current_signals = list(set(session.active_signals + proposed_signals))
        mgr.update_session(session_id, active_signals=current_signals)

        readiness = session.intake_readiness
        from server.intake_tracker import IntakeTracker
        tracker = IntakeTracker.from_dict(session.intake_fields)

        effective_stage = (
            req.deal_stage
            or tracker.get_status().get("deal_stage")
            or (session.deal_snapshot.stage if session.deal_snapshot else None)
        )
        if effective_stage:
            snap = session.deal_snapshot or DealSnapshot(stage=effective_stage)
            snap.stage = effective_stage
            mgr.update_session(session_id, deal_snapshot=snap)
            readiness.deal_stage = "present"
            tracker.set_field("deal_stage", effective_stage)
            mgr.update_session(session_id, intake_fields=tracker.to_dict())

        if current_signals:
            readiness.signals_confirmed = True
        mgr.update_session(session_id, intake_readiness=readiness)

        # Readiness check
        check = check_readiness(readiness)
        if not check["ready"]:
            mgr.update_session(session_id, state="INTAKE")
            return {"state": "INTAKE", "missing": check["missing"]}

        # Run the Decision Engine (S6 EVALUATING → S7 PATTERN_DIAGNOSTICS)
        deal_stage = readiness.deal_stage
        if session.deal_snapshot:
            deal_stage = session.deal_snapshot.stage
        elif req.deal_stage:
            deal_stage = req.deal_stage

        return _run_engine_and_store(
            engine, schema_store, mgr, session_id,
            current_signals, deal_stage, session.lever_states,
        )

    # ------------------------------------------------------------------
    # Pattern diagnostics confirmation (S7)
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/confirm-patterns")
    def confirm_patterns(session_id: str, req: ConfirmPatternsRequest):
        """S7→S8: Confirm or reject the activated pattern group."""
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != "PATTERN_DIAGNOSTICS":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot confirm patterns in state {session.state}",
            )

        activated_keys = (
            ([session.active_patterns.primary] if session.active_patterns.primary else [])
            + session.active_patterns.secondary
        )
        activated_patterns = schema_store.get_patterns_by_keys(activated_keys)

        result = process_pattern_confirmation(
            activated_patterns=activated_patterns,
            response=req.response,
            confirmed_keys=req.confirmed_keys,
        )

        next_state = result["next_state"]
        confirmed_keys = result["confirmed_patterns"]

        if next_state == "INTAKE":
            mgr.update_session(
                session_id,
                state="INTAKE",
                active_patterns=ActivePatterns(),
                selected_strategy_path=None,
                active_signals=[],
            )
            return {"state": "INTAKE"}

        # S7→S8: PRESENTING_DIAGNOSIS
        primary = confirmed_keys[0] if confirmed_keys else None
        secondary = confirmed_keys[1:] if len(confirmed_keys) > 1 else []
        mgr.update_session(
            session_id,
            state=next_state,
            active_patterns=ActivePatterns(primary=primary, secondary=secondary),
        )
        mgr.append_history(session_id, {
            "type": "patterns_confirmed",
            "confirmed_patterns": confirmed_keys,
        })

        # Build structured explanation (spec S8 rendering order)
        sp_key = session.selected_strategy_path
        sp = schema_store.get_strategy_path(sp_key) if sp_key else None
        action_objects = _resolve_actions(schema_store, sp.representative_actions if sp else [])

        primary_pattern = schema_store.get_pattern(primary) if primary else None
        explanation = _build_explanation(primary_pattern, sp)

        return {
            "state": next_state,
            "confirmed_patterns": confirmed_keys,
            "strategy_path": sp_key,
            "representative_actions": action_objects,
            "explanation": explanation,
            "understanding_prompt": "Does this match how you're seeing it?",
        }

    # ------------------------------------------------------------------
    # Confirm understanding (S8→ALIGNMENT_CHECKPOINT)
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/confirm-understanding")
    def confirm_understanding(session_id: str, req: ConfirmUnderstandingRequest):
        """S8→ALIGNMENT_CHECKPOINT: User confirms understanding of diagnosis."""
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != "PRESENTING_DIAGNOSIS":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot confirm understanding in state {session.state}",
            )

        if req.response == "clarify":
            return {"state": "PRESENTING_DIAGNOSIS", "action": "clarify"}

        # req.response == "confirm" → advance to ALIGNMENT_CHECKPOINT
        sp_key = session.selected_strategy_path
        sp = schema_store.get_strategy_path(sp_key) if sp_key else None
        primary = session.active_patterns.primary
        primary_pattern = schema_store.get_pattern(primary) if primary else None

        mgr.update_session(session_id, state="ALIGNMENT_CHECKPOINT")
        return {
            "state": "ALIGNMENT_CHECKPOINT",
            "primary_pattern": primary or "",
            "lever_states": session.lever_states,
            "strategy_path": sp_key or "",
            "primary_pattern_name": primary_pattern.name if primary_pattern else "",
            "strategy_path_name": sp.display_name if sp else "",
        }

    # ------------------------------------------------------------------
    # Alignment Checkpoint (ALIGNMENT_CHECKPOINT → ACTION_SELECTION / INTAKE)
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/alignment-checkpoint")
    def alignment_checkpoint(session_id: str, req: AlignmentCheckpointRequest):
        """Handle ALIGNMENT_CHECKPOINT responses."""
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != "ALIGNMENT_CHECKPOINT":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot handle alignment checkpoint in state {session.state}",
            )

        if req.response == "aligned":
            secondary = session.active_patterns.secondary or []
            sp_key = session.selected_strategy_path
            sp = schema_store.get_strategy_path(sp_key) if sp_key else None
            action_objects = _resolve_actions(schema_store, sp.representative_actions if sp else [])

            if secondary:
                mgr.update_session(session_id, state="DUAL_PATTERN_TRADEOFF")
                return {
                    "state": "DUAL_PATTERN_TRADEOFF",
                    "representative_actions": action_objects,
                }
            else:
                mgr.update_session(session_id, state="ACTION_SELECTION")
                return {
                    "state": "ACTION_SELECTION",
                    "representative_actions": action_objects,
                }

        elif req.response == "does_not_match":
            mgr.update_session(
                session_id,
                state="INTAKE",
                active_patterns=ActivePatterns(),
                selected_strategy_path=None,
                active_signals=[],
            )
            return {"state": "INTAKE"}

        elif req.response == "something_changed":
            mgr.update_session(
                session_id,
                state="INTAKE",
                active_patterns=ActivePatterns(),
                selected_strategy_path=None,
            )
            return {"state": "INTAKE", "re_entry": True}

        elif req.response == "new_session":
            new_session = mgr.create_session(session.user_id, session.opportunity_id)
            mgr.update_session(new_session.session_id, state="INTENT_CAPTURE")
            return {
                "state": "INTENT_CAPTURE",
                "session_id": new_session.session_id,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid response: {req.response}",
            )

    # ------------------------------------------------------------------
    # Monitoring continuation actions
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/monitoring-action")
    def monitoring_action(session_id: str, req: MonitoringActionRequest):
        """Handle monitoring continuation actions."""
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != "MONITORING":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot perform monitoring action in state {session.state}",
            )

        if req.action == "exit_for_now":
            mgr.update_session(session_id, state="SESSION_PAUSED")
            return {"state": "SESSION_PAUSED", "message": "Session paused. You can resume later."}

        elif req.action == "address_next_issue":
            current_primary = session.active_patterns.primary
            excluded = list(set((session.excluded_patterns or []) + ([current_primary] if current_primary else [])))
            deal_stage = session.deal_snapshot.stage if session.deal_snapshot else "3_Validation"

            result = engine.run(
                active_signals=session.active_signals,
                deal_stage=deal_stage,
                excluded_patterns=excluded,
            )

            if not result.primary_pattern:
                return {
                    "state": "MONITORING",
                    "no_more_patterns": True,
                    "message": "All patterns have been addressed. No additional issues found.",
                }

            activated_keys = (
                ([result.primary_pattern] if result.primary_pattern else [])
                + result.secondary_patterns
            )
            mgr.update_session(
                session_id,
                state="ALIGNMENT_CHECKPOINT",
                active_patterns=ActivePatterns(
                    primary=result.primary_pattern,
                    secondary=result.secondary_patterns,
                ),
                selected_strategy_path=result.strategy_path,
                lever_states=result.lever_states,
                excluded_patterns=excluded,
            )

            activated_patterns = schema_store.get_patterns_by_keys(activated_keys)
            primary_pattern = schema_store.get_pattern(result.primary_pattern) if result.primary_pattern else None
            sp = schema_store.get_strategy_path(result.strategy_path) if result.strategy_path else None

            return {
                "state": "ALIGNMENT_CHECKPOINT",
                "primary_pattern": result.primary_pattern,
                "selected_strategy_path": result.strategy_path,
                "lever_states": result.lever_states,
            }

        elif req.action == "re_evaluate":
            deal_stage = session.deal_snapshot.stage if session.deal_snapshot else "3_Validation"
            mgr.update_session(session_id, state="RE_EVALUATING")
            return {"state": "RE_EVALUATING"}

        elif req.action == "continue":
            return {"state": "MONITORING"}

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {req.action}",
            )

    # ------------------------------------------------------------------
    # Resume paused session
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/resume")
    def resume_session(session_id: str):
        """Resume a SESSION_PAUSED session back to MONITORING."""
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != "SESSION_PAUSED":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot resume session in state {session.state}",
            )

        mgr.update_session(session_id, state="MONITORING")
        session = mgr.get_session(session_id)
        return session.model_dump()

    # ------------------------------------------------------------------
    # Progress update (MONITORING)
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/progress")
    def submit_progress(session_id: str, req: ProgressUpdateRequest):
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != "MONITORING":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot submit progress in state {session.state}",
            )

        sp = schema_store.get_strategy_path(session.selected_strategy_path)
        if sp is None:
            raise HTTPException(status_code=400, detail="No strategy path active")

        evaluation = evaluate_progress(strategy_path=sp, update_text=req.update_text)

        mgr.append_history(session_id, {
            "type": "progress_update",
            "update_text": req.update_text,
            "evaluation": evaluation,
        })

        if evaluation["exit_detected"]:
            mgr.update_session(session_id, state="RE_EVALUATING")
            evaluation["state"] = "RE_EVALUATING"
        elif evaluation["transition_triggered"]:
            mgr.update_session(session_id, state="RE_EVALUATING")
            evaluation["state"] = "RE_EVALUATING"
        else:
            evaluation["state"] = "MONITORING"

        return evaluation

    # ------------------------------------------------------------------
    # Resolve RE_EVALUATING — exit or transition
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/resolve-reevaluation")
    def resolve_reevaluation(session_id: str, req: ResolveReevaluationRequest):
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != "RE_EVALUATING":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot resolve re-evaluation in state {session.state}",
            )

        if req.trigger == "exit":
            secondary = session.active_patterns.secondary if session.active_patterns else []
            if secondary:
                deal_stage = session.deal_snapshot.stage if session.deal_snapshot else None
                return _run_engine_and_store(
                    engine, schema_store, mgr, session_id,
                    session.active_signals, deal_stage, session.lever_states,
                )
            else:
                from datetime import datetime, timezone as _tz
                mgr.update_session(session_id, state="SESSION_COMPLETE")
                mgr.append_history(session_id, {
                    "type": "session_complete",
                    "reason": "exit_condition_met",
                    "timestamp": datetime.now(_tz.utc).isoformat(),
                })
                return {
                    "state": "SESSION_COMPLETE",
                    "reason": "Exit condition met — strategy path complete.",
                }

        elif req.trigger == "transition":
            deal_stage = session.deal_snapshot.stage if session.deal_snapshot else None
            return _run_engine_and_store(
                engine, schema_store, mgr, session_id,
                session.active_signals, deal_stage, session.lever_states,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid trigger: {req.trigger}. Must be 'exit' or 'transition'.",
            )

    # ------------------------------------------------------------------
    # Session list (for resumption on re-login)
    # ------------------------------------------------------------------
    @app.get("/api/sessions")
    def list_sessions(user_id: str | None = None, request: Request = None):
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id query parameter required")
        sessions = mgr.list_sessions(user_id=user_id)
        return [s.model_dump() for s in sessions]

    # ------------------------------------------------------------------
    # Action selection (S10→S11)
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/select-action")
    def select_action(session_id: str, req: SelectActionRequest):
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state not in ("ACTION_SELECTION",):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot select action in state {session.state}",
            )

        sp = schema_store.get_strategy_path(session.selected_strategy_path)
        if sp is None or req.action_key not in sp.representative_actions:
            raise HTTPException(status_code=400, detail="Invalid action key")

        action_obj = schema_store.get_representative_action(req.action_key)
        continuation = ["continue", "re_evaluate", "address_next_issue", "exit_for_now"]
        mgr.update_session(
            session_id,
            state="MONITORING",
            selected_action_key=req.action_key,
            continuation_options=continuation,
        )
        mgr.append_history(session_id, {
            "type": "action_selected",
            "action_key": req.action_key,
        })

        # Include active strategy context (spec S11)
        return {
            "state": "MONITORING",
            "action_key": req.action_key,
            "action_description": action_obj.description if action_obj else "",
            "action_ux_text": action_obj.ux_text if action_obj else "",
            "strategy_context": {
                "strategy_path": session.selected_strategy_path,
                "strategy_name": sp.display_name if sp else "",
                "current_focus": sp.strategic_focus if sp else "",
            },
            "session_options": ["continue", "re_evaluate", "address_next_issue", "exit_for_now"],
        }

    # ------------------------------------------------------------------
    # Dual pattern (S9→S10)
    # ------------------------------------------------------------------
    @app.post("/api/session/{session_id}/dual-pattern")
    def dual_pattern(session_id: str, req: DualPatternRequest):
        session = mgr.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.state != "DUAL_PATTERN_TRADEOFF":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot handle dual pattern in state {session.state}",
            )

        mgr.update_session(session_id, state="ACTION_SELECTION")
        mgr.append_history(session_id, {
            "type": "dual_pattern_choice",
            "choice": req.choice,
        })
        return {"state": "ACTION_SELECTION", "choice": req.choice}

    # ------------------------------------------------------------------
    # General Assist
    # ------------------------------------------------------------------
    @app.post("/api/general-assist")
    def general_assist_endpoint(req: GeneralAssistRequest):
        set_session_context(None)
        response = assist(req.content)
        return {"response": response}

    # ------------------------------------------------------------------
    # Schema (debug/admin)
    # ------------------------------------------------------------------
    @app.get("/api/schema/signals")
    def list_signals():
        return [s.model_dump() for s in schema_store.signals_sorted()]

    @app.get("/api/schema/patterns")
    def list_patterns():
        return [p.model_dump() for p in schema_store.patterns]

    @app.get("/api/schema/strategy-paths")
    def list_strategy_paths():
        return [sp.model_dump() for sp in schema_store.strategy_paths]

    @app.get("/api/schema/levers")
    def list_levers():
        return [l.model_dump() for l in schema_store.levers]

    @app.get("/api/schema/sales-zones")
    def list_sales_zones():
        return [z.model_dump() for z in schema_store.sales_zones]

    @app.get("/api/schema/representative-actions")
    def list_representative_actions():
        return [a.model_dump() for a in schema_store.representative_actions]

    # ------------------------------------------------------------------
    # Pipeline Risk Snapshot
    # ------------------------------------------------------------------
    @app.post("/api/snapshot/generate", status_code=201)
    def generate_snapshot_endpoint(
        request: Request,
        req: SnapshotGenerateRequest = SnapshotGenerateRequest(),
    ):
        """Generate (or re-generate) the snapshot for the specified week.

        Requires the caller to be authenticated and hold the snapshot.generate
        app role (assigned in Entra External ID). In local dev (no Easy Auth),
        the role check is skipped automatically.

        Omit week_start / week_end to use the current calendar week (Sunday–Saturday UTC).
        Pass explicit dates for the Azure scheduled job or manual backfills.
        Idempotent within a week — calling twice overwrites the stored document.

        Returns: snapshot metadata + HTML (primary) + Markdown (secondary).
        """
        if is_authenticated(request) and not has_role(request, SNAPSHOT_ADMIN_ROLE):
            raise HTTPException(
                status_code=403,
                detail="snapshot.generate role required",
            )

        from datetime import date as _date
        ws = _date.fromisoformat(req.week_start) if req.week_start else None
        we = _date.fromisoformat(req.week_end) if req.week_end else None

        snapshot = generate_snapshot(mgr, schema_store, snap_store, week_start=ws, week_end=we)
        html = render_html(snapshot)
        markdown = render_markdown(snapshot)
        return {
            "snapshot_id": snapshot.snapshot_id,
            "week_start": snapshot.week_start,
            "week_end": snapshot.week_end,
            "generated_at": snapshot.generated_at,
            "html": html,
            "markdown": markdown,
        }

    @app.get("/api/snapshot/latest")
    def get_latest_snapshot():
        """Return the most recently generated snapshot document.

        Returns 404 when no snapshot has been generated yet.
        Consumers can trigger /generate first to produce one.
        """
        doc = snap_store.get_latest()
        if doc is None:
            raise HTTPException(status_code=404, detail="No snapshot generated yet")
        return doc.model_dump()

    return app


def _build_explanation(pattern, strategy_path) -> dict:
    """Build structured explanation per spec S8 rendering order."""
    if not pattern or not strategy_path:
        return {}
    return {
        "structural_condition": pattern.summary if pattern else "",
        "risk": pattern.description if pattern else "",
        "strategy": strategy_path.display_name if strategy_path else "",
        "execution_framing": strategy_path.strategic_focus if strategy_path else "",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
