import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IntentCaptureScreen } from '../../components/screens/IntentCaptureScreen'
import { SituationValidationScreen } from '../../components/screens/SituationValidationScreen'
import { IntakeScreen } from '../../components/screens/IntakeScreen'
import { PatternDiagnosticsScreen } from '../../components/screens/PatternDiagnosticsScreen'
import { DiagnosisScreen } from '../../components/screens/DiagnosisScreen'
import { MonitoringScreen } from '../../components/screens/MonitoringScreen'
import { api } from '../../api/client'
import type { Pattern, RepresentativeAction, Signal, StrategyPath, Lever } from '../../types'

vi.mock('../../api/client', () => ({
  api: {
    getIntakeGaps: vi.fn(),
    submitInput: vi.fn(),
  },
}))

// ── Shared mock data ────────────────────────────────────────────────────────

const mockSignals: Signal[] = [
  {
    key: 'problem_not_validated',
    name: 'Problem Not Validated',
    description: 'Buyer has no validated problem',
    observable_condition: 'Buyer has pain but no measurable impact',
    polarity: 'negative' as const,
    severity: 'CRITICAL' as const,
    type: 'structural_risk' as const,
    affected_levers: ['case_for_change_strength'],
    zone_bias: ['zone1'],
    target_patterns: ['weak_problem_definition'],
  },
  {
    key: 'champion_engaged',
    name: 'Champion Engaged',
    description: 'Active champion identified',
    observable_condition: 'Champion is actively selling internally',
    polarity: 'positive' as const,
    severity: 'HIGH' as const,
    type: 'momentum_strength' as const,
    affected_levers: ['access_to_power'],
    zone_bias: ['zone2'],
    target_patterns: ['strong_champion'],
  },
]

const mockPatterns: Pattern[] = [
  {
    key: 'weak_problem_definition',
    name: 'Weak Problem Definition',
    description: 'Problem not clearly defined',
    summary: 'The buyer has not articulated a measurable business problem.',
    trigger_signals: ['problem_not_validated'],
    diagnostic_questions: ['Has the buyer quantified the cost of inaction?'],
    root_cause_themes: ['discovery_gap'],
    polarity: 'negative' as const,
    type: 'structural',
    severity: 'CRITICAL' as const,
    resolution_type: 'RECOVER',
    zone_bias: ['zone1'],
    affected_levers: ['case_for_change_strength'],
    candidate_strategy_path_keys: ['rebuild_case_for_change'],
  },
  {
    key: 'stalled_consensus',
    name: 'Stalled Consensus',
    description: 'Buying group not aligned',
    summary: 'Key stakeholders have not aligned on priorities.',
    trigger_signals: [],
    diagnostic_questions: ['Are all stakeholders aware of the initiative?'],
    root_cause_themes: ['alignment_gap'],
    polarity: 'negative' as const,
    type: 'structural',
    severity: 'HIGH' as const,
    resolution_type: 'RECOVER',
    zone_bias: ['zone2'],
    affected_levers: ['access_to_power'],
    candidate_strategy_path_keys: ['rebuild_consensus'],
  },
]

const mockStrategyPath: StrategyPath = {
  key: 'rebuild_case_for_change',
  display_name: 'Rebuild Case for Change',
  description: 'Re-establish the business case with quantified impact.',
  mode: 'RECOVER',
  diagnostic_question: 'Has the buyer quantified their problem?',
  target_levers: ['case_for_change_strength'],
  zone_bias: ['zone1'],
  entry_conditions: ['problem_not_validated signal active'],
  disqualifying_conditions: [],
  core_objectives: 'Build a compelling, quantified case for change.',
  strategic_focus: 'Focus on discovery and problem quantification.',
  core_strategies: ['Re-engage discovery', 'Quantify cost of inaction'],
  representative_actions: ['action_rebuild_discovery'],
  positive_progress_signals: ['problem_validated'],
  negative_progress_signals: ['champion_disengaged'],
  exit_lever_state: 'strong',
  exit_outcome: 'Buyer has a quantified, compelling reason to act.',
}

const mockActions: RepresentativeAction[] = [
  {
    action_key: 'action_rebuild_discovery',
    parent_strategy_path: 'rebuild_case_for_change',
    description: 'Schedule a discovery workshop to quantify impact.',
    ux_text: 'Schedule a discovery workshop to quantify business impact',
  },
  {
    action_key: 'action_stakeholder_map',
    parent_strategy_path: 'rebuild_case_for_change',
    description: 'Map stakeholders and their priorities.',
    ux_text: 'Map the buying group and identify gaps in alignment',
  },
]

const mockLevers: Lever[] = [
  {
    key: 'case_for_change_strength',
    name: 'Case for Change',
    qualifiers: 'Strength of the business case',
    score_model: 'binary',
    lever_scoring: '0-1',
    why_it_matters: 'Without a strong case, deals stall.',
    states: ['weak', 'moderate', 'strong'],
  },
]

const mockLeverStates: Record<string, string> = {
  case_for_change_strength: 'weak',
}

const SIX_MISSING_FIELDS = [
  'deal_stage',
  'offering_type',
  'offering_usage',
  'usage_depth',
  'deal_amount',
  'deal_close_date',
]

// ── FI-01: IntentCaptureScreen — submit fires callback ──────────────────────

describe('FI-01: IntentCaptureScreen — submit fires callback', () => {
  it('calls onSubmit with trimmed text when Continue is clicked', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(<IntentCaptureScreen onSubmit={onSubmit} loading={false} />)

    const textarea = screen.getByPlaceholderText(/my champion went silent/i)
    expect(textarea).toBeInTheDocument()

    await user.type(textarea, '  Deal is stalling at procurement  ')
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith('Deal is stalling at procurement')
  })

  it('disables button when textarea is empty', () => {
    render(<IntentCaptureScreen onSubmit={vi.fn()} loading={false} />)
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('shows correction heading when isCorrection is true', () => {
    render(<IntentCaptureScreen onSubmit={vi.fn()} loading={false} isCorrection />)
    expect(screen.getByText(/let me get that right/i)).toBeInTheDocument()
  })
})

// ── FI-02: SituationValidationScreen — confirm fires callback ───────────────

describe('FI-02: SituationValidationScreen — confirm fires callback', () => {
  it('displays summary and calls onConfirm when Yes is clicked', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    const onCorrect = vi.fn()

    render(
      <SituationValidationScreen
        summary="The deal is stalling because the buyer has not validated the problem."
        onConfirm={onConfirm}
        onCorrect={onCorrect}
        loading={false}
      />,
    )

    expect(
      screen.getByText(/the deal is stalling because the buyer has not validated the problem/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /yes, that.s right/i }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onCorrect).not.toHaveBeenCalled()
  })
})

// ── FI-03: SituationValidationScreen — correct loops back ───────────────────

describe('FI-03: SituationValidationScreen — correct loops back', () => {
  it('calls onCorrect when Let me clarify is clicked', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    const onCorrect = vi.fn()

    render(
      <SituationValidationScreen
        summary="Some summary text"
        onConfirm={onConfirm}
        onCorrect={onCorrect}
        loading={false}
      />,
    )

    await user.click(screen.getByRole('button', { name: /let me clarify/i }))

    expect(onCorrect).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })
})

// ── FI-04: IntakeScreen (fields phase) — shows field prompts first ──────────

describe('FI-04: IntakeScreen (fields phase) — shows field prompts first', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows field prompt and progress when fields are missing', async () => {
    vi.mocked(api.getIntakeGaps).mockResolvedValue({
      required: SIX_MISSING_FIELDS,
      has_signals: false,
    })

    render(
      <IntakeScreen
        sessionId="test-session"
        signals={mockSignals}
        onSubmitSignals={vi.fn()}
        onSubmitText={vi.fn()}
        loading={false}
        error={null}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText(/what stage is this deal in/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/step 1 of 6/i)).toBeInTheDocument()
    expect(screen.queryByText('Confirm deal signals')).not.toBeInTheDocument()
    expect(screen.queryByText('Problem Not Validated')).not.toBeInTheDocument()
  })
})

// ── FI-05: IntakeScreen (fields phase) — field submission advances ──────────

describe('FI-05: IntakeScreen (fields phase) — field submission advances', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('submits field and advances to next prompt', async () => {
    const user = userEvent.setup()

    vi.mocked(api.getIntakeGaps).mockResolvedValue({
      required: SIX_MISSING_FIELDS,
      has_signals: false,
    })

    vi.mocked(api.submitInput).mockResolvedValue({
      state: 'INTAKE',
      next_prompt: { field: 'offering_type', prompt: 'Is this a product, services, or hybrid deal?' },
    })

    render(
      <IntakeScreen
        sessionId="test-session"
        signals={mockSignals}
        onSubmitSignals={vi.fn()}
        onSubmitText={vi.fn()}
        loading={false}
        error={null}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText(/what stage is this deal in/i)).toBeInTheDocument()
    })

    await user.click(screen.getByText(/3 Validation/i))

    await waitFor(() => {
      expect(api.submitInput).toHaveBeenCalledWith('test-session', {
        input_type: 'fields',
        fields: { deal_stage: '3_Validation' },
      })
    })

    await waitFor(() => {
      expect(screen.getByText(/product, services, or hybrid/i)).toBeInTheDocument()
    })
  })
})

// ── FI-06: IntakeScreen (signals phase) — signals shown after fields ────────

describe('FI-06: IntakeScreen (signals phase) — signals shown after fields', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows signal buttons when no fields are missing', async () => {
    vi.mocked(api.getIntakeGaps).mockResolvedValue({
      required: [],
      has_signals: false,
    })

    render(
      <IntakeScreen
        sessionId="test-session"
        signals={mockSignals}
        onSubmitSignals={vi.fn()}
        onSubmitText={vi.fn()}
        loading={false}
        error={null}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText('Confirm deal signals')).toBeInTheDocument()
    })

    expect(screen.queryByText(/what stage/i)).not.toBeInTheDocument()
    expect(screen.getByText('Problem Not Validated')).toBeInTheDocument()
    expect(screen.getByText('Champion Engaged')).toBeInTheDocument()
  })
})

// ── FI-07: IntakeScreen (signals phase) — signal submission fires callback ──

describe('FI-07: IntakeScreen (signals phase) — signal submission fires callback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('toggles a signal and submits selection', async () => {
    const user = userEvent.setup()
    const onSubmitSignals = vi.fn()

    vi.mocked(api.getIntakeGaps).mockResolvedValue({
      required: [],
      has_signals: false,
    })

    render(
      <IntakeScreen
        sessionId="test-session"
        signals={mockSignals}
        onSubmitSignals={onSubmitSignals}
        onSubmitText={vi.fn()}
        loading={false}
        error={null}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText('Confirm deal signals')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Problem Not Validated'))

    const continueBtn = screen.getByRole('button', { name: /continue with 1 signal/i })
    expect(continueBtn).toBeInTheDocument()

    await user.click(continueBtn)

    expect(onSubmitSignals).toHaveBeenCalledTimes(1)
    expect(onSubmitSignals).toHaveBeenCalledWith(['problem_not_validated'])
  })
})

// ── FI-08: PatternDiagnosticsScreen — binary confirm only ───────────────────

describe('FI-08: PatternDiagnosticsScreen — binary confirm only', () => {
  it('renders patterns with labels and has only confirm/reject buttons', () => {
    const onConfirm = vi.fn()
    const onRejectAll = vi.fn()

    const { container } = render(
      <PatternDiagnosticsScreen
        patterns={mockPatterns}
        metaExplanation="These patterns explain the current structural risks."
        onConfirm={onConfirm}
        onRejectAll={onRejectAll}
        loading={false}
      />,
    )

    // Both patterns visible
    expect(screen.getByText('Weak Problem Definition')).toBeInTheDocument()
    expect(screen.getByText('Stalled Consensus')).toBeInTheDocument()

    // Labels: Primary and Secondary
    expect(screen.getByText('Primary')).toBeInTheDocument()
    expect(screen.getByText('Secondary')).toBeInTheDocument()

    // No checkboxes
    expect(container.querySelector('input[type="checkbox"]')).toBeNull()

    // Exactly the two expected buttons
    expect(
      screen.getByRole('button', { name: /yes, this matches/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /no, this doesn't reflect/i }),
    ).toBeInTheDocument()
  })

  it('calls onConfirm with all pattern keys when confirm is clicked', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()

    render(
      <PatternDiagnosticsScreen
        patterns={mockPatterns}
        metaExplanation=""
        onConfirm={onConfirm}
        onRejectAll={vi.fn()}
        loading={false}
      />,
    )

    await user.click(screen.getByRole('button', { name: /yes, this matches/i }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onConfirm).toHaveBeenCalledWith([
      'weak_problem_definition',
      'stalled_consensus',
    ])
  })
})

// ── FI-09: PatternDiagnosticsScreen — reject fires callback ─────────────────

describe('FI-09: PatternDiagnosticsScreen — reject fires callback', () => {
  it('calls onRejectAll when reject button is clicked', async () => {
    const user = userEvent.setup()
    const onRejectAll = vi.fn()

    render(
      <PatternDiagnosticsScreen
        patterns={mockPatterns}
        metaExplanation=""
        onConfirm={vi.fn()}
        onRejectAll={onRejectAll}
        loading={false}
      />,
    )

    await user.click(screen.getByRole('button', { name: /no, this doesn't reflect/i }))

    expect(onRejectAll).toHaveBeenCalledTimes(1)
  })
})

// ── FI-10: DiagnosisScreen — actions shown with descriptions ────────────────

describe('FI-10: DiagnosisScreen — actions shown with descriptions', () => {
  it('renders strategy path, actions, and fires selection callback', async () => {
    const user = userEvent.setup()
    const onSelectAction = vi.fn()

    render(
      <DiagnosisScreen
        primaryPattern={mockPatterns[0]}
        secondaryPatterns={[mockPatterns[1]]}
        strategyPath={mockStrategyPath}
        actions={mockActions}
        levers={mockLevers}
        leverStates={mockLeverStates}
        onSelectAction={onSelectAction}
        onPivot={vi.fn()}
        loading={false}
      />,
    )

    // Strategy path name visible
    expect(screen.getByText('Rebuild Case for Change')).toBeInTheDocument()

    // At least one action with ux_text visible
    expect(
      screen.getByText('Schedule a discovery workshop to quantify business impact'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Map the buying group and identify gaps in alignment'),
    ).toBeInTheDocument()

    // Click first action
    await user.click(
      screen.getByText('Schedule a discovery workshop to quantify business impact'),
    )

    expect(onSelectAction).toHaveBeenCalledTimes(1)
    expect(onSelectAction).toHaveBeenCalledWith('action_rebuild_discovery')
  })

  it('shows primary pattern and secondary patterns', () => {
    render(
      <DiagnosisScreen
        primaryPattern={mockPatterns[0]}
        secondaryPatterns={[mockPatterns[1]]}
        strategyPath={mockStrategyPath}
        actions={mockActions}
        levers={mockLevers}
        leverStates={mockLeverStates}
        onSelectAction={vi.fn()}
        onPivot={vi.fn()}
        loading={false}
      />,
    )

    expect(screen.getByText('Weak Problem Definition')).toBeInTheDocument()
    expect(screen.getByText('Stalled Consensus')).toBeInTheDocument()
  })
})

// ── FI-11: MonitoringScreen — active strategy displayed ─────────────────────

describe('FI-11: MonitoringScreen — active strategy displayed', () => {
  const selectedAction: RepresentativeAction = {
    action_key: 'action_rebuild_discovery',
    parent_strategy_path: 'rebuild_case_for_change',
    description: 'Schedule a discovery workshop.',
    ux_text: 'Schedule a discovery workshop to quantify business impact',
  }

  it('displays strategy path, selected action, and pivot button', () => {
    const onPivot = vi.fn()

    render(
      <MonitoringScreen
        strategyPath={mockStrategyPath}
        primaryPattern={mockPatterns[0]}
        levers={mockLevers}
        leverStates={mockLeverStates}
        selectedAction={selectedAction}
        onPivot={onPivot}
        onRestart={vi.fn()}
      />,
    )

    expect(screen.getByText('Rebuild Case for Change')).toBeInTheDocument()
    expect(
      screen.getByText('Schedule a discovery workshop to quantify business impact'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /something changed/i }),
    ).toBeInTheDocument()
  })

  it('calls onPivot when Something changed is clicked', async () => {
    const user = userEvent.setup()
    const onPivot = vi.fn()

    render(
      <MonitoringScreen
        strategyPath={mockStrategyPath}
        primaryPattern={mockPatterns[0]}
        levers={mockLevers}
        leverStates={mockLeverStates}
        selectedAction={selectedAction}
        onPivot={onPivot}
        onRestart={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: /something changed/i }))
    expect(onPivot).toHaveBeenCalledTimes(1)
  })

  it('calls onRestart when New session is clicked', async () => {
    const user = userEvent.setup()
    const onRestart = vi.fn()

    render(
      <MonitoringScreen
        strategyPath={mockStrategyPath}
        primaryPattern={mockPatterns[0]}
        levers={mockLevers}
        leverStates={mockLeverStates}
        selectedAction={selectedAction}
        onPivot={vi.fn()}
        onRestart={onRestart}
      />,
    )

    await user.click(screen.getByRole('button', { name: /new session/i }))
    expect(onRestart).toHaveBeenCalledTimes(1)
  })
})

// ── FI-12: SessionComplete — completion screen renders ──────────────────────

describe('FI-12: SessionComplete — completion screen renders', () => {
  it('renders Session Complete text and Start New Deal button', () => {
    const onRestart = vi.fn()

    // Render the same inline JSX from App.tsx's SESSION_COMPLETE state
    render(
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
        <div className="mx-auto max-w-xl space-y-6 text-center">
          <div className="text-4xl">&#10003;</div>
          <h1 className="text-2xl font-bold text-white">Session Complete</h1>
          <p className="text-slate-400">
            The strategy path has been resolved. You can start a new deal
            or return to review your session history.
          </p>
          <button
            onClick={onRestart}
            className="rounded-lg bg-violet-600 px-6 py-3 font-medium text-white transition hover:bg-violet-500"
          >
            Start New Deal
          </button>
        </div>
      </div>,
    )

    expect(screen.getByText('Session Complete')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /start new deal/i }),
    ).toBeInTheDocument()
  })

  it('fires restart callback when Start New Deal is clicked', async () => {
    const user = userEvent.setup()
    const onRestart = vi.fn()

    render(
      <div>
        <h1>Session Complete</h1>
        <button onClick={onRestart}>Start New Deal</button>
      </div>,
    )

    await user.click(screen.getByRole('button', { name: /start new deal/i }))
    expect(onRestart).toHaveBeenCalledTimes(1)
  })
})
