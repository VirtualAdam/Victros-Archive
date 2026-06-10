import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StartScreen } from '../../components/screens/StartScreen'

describe('StartScreen', () => {
  it('renders the title and fields', () => {
    render(<StartScreen onStart={vi.fn()} onResume={vi.fn()} />)
    expect(screen.getByText('Victros')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/jane_doe/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/acme_q2_security/i)).toBeInTheDocument()
  })

  it('submit button is disabled when fields are empty', () => {
    render(<StartScreen onStart={vi.fn()} onResume={vi.fn()} />)
    expect(screen.getByRole('button', { name: /start session/i })).toBeDisabled()
  })

  it('calls onStart with userId and opportunityId', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<StartScreen onStart={onStart} onResume={vi.fn()} />)

    await user.type(screen.getByPlaceholderText(/jane_doe/i), 'alice')
    await user.type(screen.getByPlaceholderText(/acme_q2/i), 'deal_001')
    await user.click(screen.getByRole('button', { name: /start session/i }))

    expect(onStart).toHaveBeenCalledWith('alice', 'deal_001')
  })

  it('shows error message when error prop is set', () => {
    render(<StartScreen onStart={vi.fn()} onResume={vi.fn()} error="Network error" />)
    expect(screen.getByText('Network error')).toBeInTheDocument()
  })
})
