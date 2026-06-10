import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IntentCaptureScreen } from '../../components/screens/IntentCaptureScreen'

describe('IntentCaptureScreen', () => {
  it('renders the initial prompt', () => {
    render(<IntentCaptureScreen onSubmit={vi.fn()} loading={false} />)
    expect(screen.getByText('How can I help you win today?')).toBeInTheDocument()
  })

  it('renders the correction prompt when isCorrection is true', () => {
    render(<IntentCaptureScreen onSubmit={vi.fn()} loading={false} isCorrection />)
    expect(screen.getByText(/let me get that right/i)).toBeInTheDocument()
  })

  it('submit button is disabled when text is empty', () => {
    render(<IntentCaptureScreen onSubmit={vi.fn()} loading={false} />)
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('calls onSubmit with trimmed text', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<IntentCaptureScreen onSubmit={onSubmit} loading={false} />)

    await user.type(screen.getByRole('textbox'), '  My champion went silent  ')
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(onSubmit).toHaveBeenCalledWith('My champion went silent')
  })

  it('disables input and button when loading', () => {
    render(<IntentCaptureScreen onSubmit={vi.fn()} loading={true} />)
    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button')).toBeDisabled()
  })
})
