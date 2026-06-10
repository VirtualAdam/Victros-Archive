import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SituationValidationScreen } from '../../components/screens/SituationValidationScreen'

describe('SituationValidationScreen', () => {
  const defaultProps = {
    summary: 'Deal where buyer has pain but cannot quantify impact.',
    onConfirm: vi.fn(),
    onCorrect: vi.fn(),
    loading: false,
  }

  it('renders the situation summary', () => {
    render(<SituationValidationScreen {...defaultProps} />)
    expect(screen.getByText(defaultProps.summary)).toBeInTheDocument()
  })

  it('renders confirm and correct buttons', () => {
    render(<SituationValidationScreen {...defaultProps} />)
    expect(screen.getByRole('button', { name: /yes/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /clarify/i })).toBeInTheDocument()
  })

  it('calls onConfirm when confirm button is clicked', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(<SituationValidationScreen {...defaultProps} onConfirm={onConfirm} />)

    await user.click(screen.getByRole('button', { name: /yes/i }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('calls onCorrect when clarify button is clicked', async () => {
    const user = userEvent.setup()
    const onCorrect = vi.fn()
    render(<SituationValidationScreen {...defaultProps} onCorrect={onCorrect} />)

    await user.click(screen.getByRole('button', { name: /clarify/i }))
    expect(onCorrect).toHaveBeenCalledOnce()
  })

  it('disables buttons when loading', () => {
    render(<SituationValidationScreen {...defaultProps} loading={true} />)
    expect(screen.getByRole('button', { name: /processing/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /clarify/i })).toBeDisabled()
  })
})
