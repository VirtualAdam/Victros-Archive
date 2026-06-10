import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmationScreen } from '../../components/screens/ConfirmationScreen'

const baseProposal = {
  signals: [
    { label: 'Single-Threaded Contact', value: 'single_threaded_contact' },
    { label: 'Competition Gaining Mindshare', value: 'competition_gaining_mindshare' },
  ],
  deal_attributes: [{ label: 'Stage', value: '3_Validation' }],
  summary: 'Two risks detected.',
}

describe('ConfirmationScreen', () => {
  it('renders detected signals', () => {
    render(
      <ConfirmationScreen
        proposal={baseProposal}
        onConfirm={vi.fn()}
        onAdjust={vi.fn()}
        onReject={vi.fn()}
      />,
    )
    expect(screen.getByText('Single-Threaded Contact')).toBeInTheDocument()
    expect(screen.getByText('Competition Gaining Mindshare')).toBeInTheDocument()
  })

  it('calls onConfirm when Yes is clicked', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <ConfirmationScreen
        proposal={baseProposal}
        onConfirm={onConfirm}
        onAdjust={vi.fn()}
        onReject={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /yes/i }))
    expect(onConfirm).toHaveBeenCalledWith('3_Validation')
  })

  it('calls onAdjust when Adjust is clicked', async () => {
    const user = userEvent.setup()
    const onAdjust = vi.fn()
    render(
      <ConfirmationScreen
        proposal={baseProposal}
        onConfirm={vi.fn()}
        onAdjust={onAdjust}
        onReject={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /adjust/i }))
    expect(onAdjust).toHaveBeenCalled()
  })

  it('calls onReject when Not correct is clicked', async () => {
    const user = userEvent.setup()
    const onReject = vi.fn()
    render(
      <ConfirmationScreen
        proposal={baseProposal}
        onConfirm={vi.fn()}
        onAdjust={vi.fn()}
        onReject={onReject}
      />,
    )
    await user.click(screen.getByRole('button', { name: /not correct/i }))
    expect(onReject).toHaveBeenCalled()
  })
})
