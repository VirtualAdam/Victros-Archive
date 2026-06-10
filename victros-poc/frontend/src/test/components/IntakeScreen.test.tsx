import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IntakeScreen } from '../../components/screens/IntakeScreen'
import { api } from '../../api/client'

// Mock the API module
vi.mock('../../api/client', () => ({
  api: {
    getIntakeGaps: vi.fn(),
    submitInput: vi.fn(),
  },
}))

const mockSignals = [
  {
    key: 'problem_not_validated',
    name: 'Problem Not Validated',
    polarity: 'negative' as const,
    severity: 'CRITICAL' as const,
    type: 'structural_risk' as const,
    observable_condition: 'Buyer has pain but no measurable impact',
    affected_levers: ['case_for_change_strength'],
    target_patterns: ['weak_problem_definition'],
    zone_bias: ['zone1'],
    description: '',
    trigger_input_conditions: '',
  },
]

describe('IntakeScreen — field-first flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows field prompts BEFORE signal buttons when fields are missing', async () => {
    // Backend says: all 6 fields missing, no signals
    vi.mocked(api.getIntakeGaps).mockResolvedValue({
      required: [
        'deal_stage',
        'offering_type',
        'offering_usage',
        'usage_depth',
        'deal_amount',
        'deal_close_date',
      ],
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

    // Should show the FIRST field prompt, not signals
    await waitFor(() => {
      expect(screen.getByText(/what stage/i)).toBeInTheDocument()
    })

    // Signal buttons should NOT be visible yet
    expect(screen.queryByText('Confirm deal signals')).not.toBeInTheDocument()
    expect(screen.queryByText('Problem Not Validated')).not.toBeInTheDocument()
  })

  it('shows signal buttons AFTER all fields are collected', async () => {
    // Backend says: no fields missing
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

    // Should show signals, not field prompts
    await waitFor(() => {
      expect(screen.getByText('Confirm deal signals')).toBeInTheDocument()
    })

    // Field prompts should NOT be visible
    expect(screen.queryByText(/what stage/i)).not.toBeInTheDocument()
  })

  it('advances from one field to the next on submit', async () => {
    const user = userEvent.setup()

    vi.mocked(api.getIntakeGaps).mockResolvedValue({
      required: ['deal_stage', 'offering_type', 'offering_usage', 'usage_depth', 'deal_amount', 'deal_close_date'],
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

    // Wait for first field
    await waitFor(() => {
      expect(screen.getByText(/what stage/i)).toBeInTheDocument()
    })

    // Click a stage option
    await user.click(screen.getByText(/3 Validation/i))

    // API should have been called with the field
    await waitFor(() => {
      expect(api.submitInput).toHaveBeenCalledWith('test-session', {
        input_type: 'fields',
        fields: { deal_stage: '3_Validation' },
      })
    })

    // Next field should appear
    await waitFor(() => {
      expect(screen.getByText(/product, services, or hybrid/i)).toBeInTheDocument()
    })
  })

  it('shows progress indicator with correct step count', async () => {
    vi.mocked(api.getIntakeGaps).mockResolvedValue({
      required: ['deal_stage', 'offering_type', 'offering_usage', 'usage_depth', 'deal_amount', 'deal_close_date'],
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
      expect(screen.getByText(/step 1 of 6/i)).toBeInTheDocument()
    })
  })
})
