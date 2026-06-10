# Victros — Test Report

**Last run:** 2026-04-24
**Backend version:** 1.3.0 (SRS gap remediation)
**Frontend version:** UI:E
**Result:** 4,137 backend passed | 54 frontend component passed (4 stale) | 12 browser smoke passed | 4 auth enforcement passed

---

## Test Strategy Overview

Tests are organized into seven layers, each catching a different class of failure:

| Layer | Tool | Purpose | Catches |
|-------|------|---------|---------|
| **Engine & Logic** | pytest | Validate deterministic pipeline (E1–E6), PatternWeight, tiebreakers | Logic bugs in signal→pattern→strategy flow |
| **API E2E** | pytest + TestClient | Drive full HTTP flows through every state transition | API not enforcing state machine |
| **Frontend Contract** | pytest | Cross-reference backend states against frontend handlers | State mismatch between layers |
| **Frontend Build Gate** | pytest + tsc | Run `tsc --noEmit` on frontend source | TypeScript/JSX compilation errors |
| **Component Tests** | Vitest | Render frontend screens and test interactions with mocked API | Screen rendering and callback errors |
| **Frontend Integration** | Vitest | Render screens, simulate user flow, assert correct API calls fire | Wrong UI shown for a given state |
| **Browser Smoke** | Playwright | Load live app in headless Chrome, click through a deal scenario | Auth loops, blank pages, real browser rendering failures |
| **Auth Enforcement** | pytest + httpx / Playwright | Verify SWA rejects unauthenticated requests and redirects to login | Auth misconfiguration, unprotected routes |

Additional confidence strategies:

| Strategy | Tool | Purpose |
|----------|------|---------|
| **Mutation Testing** | pytest + monkeypatch | Deliberately break engine logic, verify tests detect it |
| **Invariant Testing** | pytest | Assert structural rules hold for ANY signal combination |
| **Golden Tests** | pytest | Richard's UAT deal scenarios with HIS expected outcomes |
| **API Smoke** | pytest + httpx | Hit live backend endpoints after deploy |

---

## Backend Test Files (40 files, 4,137 tests)

| File | Tests | Category | Description |
|------|-------|----------|-------------|
| `test_invariants.py` | 3,561 | Engine | 12 invariants × 328 signal combinations (singles, pairs, triples, all) |
| `test_data_flow_logic.py` | 82 | Engine | Every entry/exit guard and pipeline step from data-flow-logic.md |
| `test_decision_engine.py` | 38 | Engine | Pattern activation, collision resolution, strategy path selection, quality gates |
| `test_signal_validation.py` | 8 | Engine | Structural preconditions, confidence filtering, evidence requirements |
| `test_signal_derivation_flow.py` | 6 | Engine | Auto-extraction after intake, confidence scores, user confirm/reject |
| `test_signal_quality_gates.py` | 7 | Engine | Lever coverage gaps, critical gap blocking, polarity balance |
| `test_strategy_ranking.py` | 9 | Engine | Multi-factor composite ranking: lever alignment, resolution type, entry conditions |
| `test_decision_snapshot.py` | 9 | Feature | Per-evaluation snapshots: auto-capture, re-evaluation, persistence, diffing |
| `test_alignment_checkpoint.py` | 7 | State | ALIGNMENT_CHECKPOINT state, 4 checkpoint options, pattern exclusion |
| `test_monitoring_continuation.py` | 8 | State | Monitoring continuation: stay course, next issue, exit, new session |
| `test_snapshot_service.py` | 29 | Feature | Pipeline Risk Snapshot generation and rendering |
| `test_state_machine.py` | 28 | State | Valid and invalid state transitions, ALIGNMENT_CHECKPOINT, SESSION_PAUSED |
| `test_explanation_service.py` | 23 | LLM | Explanation rendering, persona voice, schema grounding |
| `test_richard_golden.py` | 22 | Golden | Richard's 5 UAT deal scenarios with his expected outcomes |
| `test_api.py` | 19 | API | Individual endpoint contract tests |
| `test_open_items.py` | 18 | API | Signal prioritization, action context, pivot retention, intake tracking |
| `test_pattern_diagnostics.py` | 17 | Engine | Pattern group formatting, binary confirmation, severity ordering |
| `test_extraction_service.py` | 17 | LLM | Signal extraction, recall, precision, pivot logic |
| `test_monitoring.py` | 15 | Feature | Progress evaluation, transition detection, exit conditions |
| `test_intake_loop.py` | 15 | Feature | IntakeTracker fields, gaps, readiness, source-agnostic filling |
| `test_session_manager.py` | 14 | CRUD | Session create, read, update, persistence |
| `test_intent_router.py` | 14 | LLM | Intent classification, F1 metrics, robustness |
| `test_auth.py` | 13 | Auth | Easy Auth header parsing, token validation |
| `test_schema_store.py` | 12 | Schema | Schema loading, cross-references, error handling |
| `test_med_implicit_items.py` | 26 | Feature | Signal normalization, PIVOT cleanup, two-loop validation, multi-pattern iteration, exit flow |
| `test_med_explicit_items.py` | 20 | Feature | Calibration notes, lever mapping, transparency summary, activation trace, action specificity, diffing, monitoring triggers |
| `test_models.py` | 15 | Models | Pydantic model validation, serialization, ActiveSignal, DecisionSnapshot |
| `test_llm_client.py` | 12 | LLM | Client factory, mock mode, force mock, dev logging |
| `test_api_e2e_flow.py` | 12 | API E2E | Full HTTP flows: happy path, TMobile, correction, rejection, dual pattern |
| `test_session_resumption.py` | 10 | Feature | Session list, sort, resume from monitoring |
| `test_session_completion.py` | 9 | Feature | RE_EVALUATING resolution, SESSION_COMPLETE, full lifecycle |
| `test_mutation_confidence.py` | 9 | Mutation | 9 deliberate engine breakages, all detected |
| `test_general_assist.py` | 12 | LLM | Coaching voice, no schema contamination |
| `test_readiness_check.py` | 5 | Feature | Intake readiness gate |
| `test_confirmation_gate.py` | 4 | Feature | Signal proposal formatting |
| `test_config.py` | 3 | Config | Environment variable loading |
| `test_frontend_contract.py` | 2 | Contract | Backend states have frontend handlers |
| `test_frontend_build.py` | 1 | Build | TypeScript compilation gate |
| `test_deploy_smoke.py` | 3 | Smoke | Live endpoint health, session create, minimal flow (run with `-m smoke`) |
| `test_auth_enforcement.py` | 4 | Auth | SWA auth enforcement: unauthenticated → 302, API rejection, login endpoint, /.auth/me (run with `-m auth`) |

---

## Frontend Test Files (11 files, 54 passing + 4 stale)

### Component Tests (Vitest)

| File | Tests | Description |
|------|-------|-------------|
| `IntentCaptureScreen.test.tsx` | 5 | Prompt rendering, correction mode, submit, loading |
| `SituationValidationScreen.test.tsx` | 5 | Summary display, confirm/correct callbacks, loading |
| `IntakeScreen.test.tsx` | 4 | Fields-first phase, field advancement, signals-after |
| `StartScreen.test.tsx` | 5 | Title, fields, submit (4 stale — needs update for auth changes) |
| `ConfirmationScreen.test.tsx` | 5 | Signal proposal rendering, confirm/reject |
| `Badge.test.tsx` | 3 | UI component rendering |
| `Button.test.tsx` | 4 | UI component variants |
| `LeverBar.test.tsx` | 3 | Lever state visualization |
| `client.test.ts` | 5 | API client request formatting |

### Integration Tests (Vitest)

| File | Tests | Description |
|------|-------|-------------|
| `screen-flow.test.tsx` | 19 | All 9 screens: renders correct UI, fires correct API calls |

---

## Browser Smoke Tests (Playwright, 16 tests)

Run against the live deployed app in headless Chrome.

| Test | What It Catches |
|------|-----------------|
| BS-01 | Backend health endpoint returns ok |
| BS-02 | Backend version endpoint returns version + iteration |
| BS-03 | Frontend loads without auth redirect loop |
| BS-04 | Version footer visible and shows API version |
| BS-05 | New session starts in INTENT_CAPTURE |
| BS-06 | Intent submission → SITUATION_VALIDATION |
| BS-07 | Situation confirm → INTAKE |
| BS-08 | Required fields advance through INTAKE to AWAITING_CONFIRMATION |
| BS-09 | Confirm → PATTERN_DIAGNOSTICS with pattern_group |
| BS-10 | Confirm patterns → PRESENTING_DIAGNOSIS with strategy_path |
| BS-11 | Confirm understanding → ACTION_SELECTION or DUAL_PATTERN_TRADEOFF |
| BS-12 | INTAKE state renders field prompts, not signals (catches IntakeScreen bug) |
| BS-AUTH-01 | Unauthenticated request to / → 302 redirect to login |
| BS-AUTH-02 | Unauthenticated API call through SWA → rejected (401 or 302) |
| BS-AUTH-03 | /.auth/login/aad endpoint redirects to Entra |
| BS-AUTH-04 | /.auth/me without session returns null clientPrincipal |

---

## How to Run

```bash
# Full backend suite (excludes integration, smoke, and auth enforcement)
cd victros-poc && python -m pytest backend/tests/ -m "not integration and not smoke and not auth" -q

# Auth enforcement tests against live SWA
cd victros-poc && python -m pytest backend/tests/ -m auth -v

# Frontend component + integration tests
cd victros-poc/frontend && npm test

# Browser smoke tests against live deployment (Playwright)
cd victros-poc/frontend && npm run test:smoke

# Browser smoke tests with visible browser
cd victros-poc/frontend && npm run test:smoke:headed

# API smoke tests against live endpoint
cd victros-poc && python -m pytest backend/tests/ -m smoke -v

# LLM evals against live gpt-4o (requires credentials)
export VICTROS_AI_ENDPOINT=""
export VICTROS_AI_KEY=""
cd victros-poc && python -m pytest backend/tests/test_intent_router.py backend/tests/test_extraction_service.py backend/tests/test_explanation_service.py backend/tests/test_general_assist.py -v

# Post-deploy verification (recommended sequence)
./deploy.sh both
cd victros-poc && python -m pytest backend/tests/ -m smoke -v
cd victros-poc && python -m pytest backend/tests/ -m auth -v
cd victros-poc/frontend && npm run test:smoke
```

---

## What Each Layer Would Have Caught

| Bug | Engine | API E2E | Contract | Build | Component | Integration | Browser Smoke | Auth Enforcement |
|-----|--------|---------|----------|-------|-----------|-------------|---------------|-----------------|
| Wrong PatternWeight | ✅ | — | — | — | — | — | — | — |
| API skips INTENT_CAPTURE | — | ✅ | — | — | — | — | ✅ | — |
| SESSION_COMPLETE no frontend handler | — | — | ✅ | — | — | — | — | — |
| JSX apostrophe / missing import | — | — | — | ✅ | — | — | — | — |
| IntakeScreen shows signals before fields | — | — | — | — | — | ✅ | ✅ | — |
| Auth redirect loop | — | — | — | — | — | — | ✅ | ✅ |
| Auth misconfigured (routes allow anonymous) | — | — | — | — | — | — | — | ✅ |
| API accessible without auth through SWA | — | — | — | — | — | — | — | ✅ |

---

## Test Run History

| Date | Backend | Frontend | Browser Smoke | Notes |
|------|---------|----------|---------------|-------|
| 2026-04-24 | 4,137 ✅ + 4 auth ✅ | 54 ✅ (4 stale) | 16 ✅ | SRS gap remediation: 8 phases, 114 new tests — signal validation, quality gates, strategy ranking, alignment checkpoint, monitoring continuation, decision snapshots, MED items |
| 2026-04-21 | 4,023 ✅ + 4 auth ✅ | 54 ✅ (4 stale) | 16 ✅ | SWA auth restored, MSAL removed, auth enforcement tests added (positive + negative) |
| 2026-04-20 | 4,023 ✅ | 54 ✅ (4 stale) | 12 ✅ | Playwright added, IntakeScreen fix, contract test caught SESSION_COMPLETE |
| 2026-04-17 | 4,008 ✅ | — | — | UAT-v1.2 engine rewrite, 82 data-flow-logic tests |
| 2026-04-14 | 334 ✅ | — | — | Session completion, monitoring, pattern diagnostics |
| 2026-04-13 | 48 ✅ | — | — | Initial LLM eval suite |
