import { render, screen } from '@testing-library/react'
import { LeverBar } from '../../components/ui/LeverBar'

describe('LeverBar', () => {
  it('shows the human-readable lever label', () => {
    render(<LeverBar leverKey="champion_strength" state="CONNECTED" />)
    expect(screen.getByText('Champion Strength')).toBeInTheDocument()
  })

  it('shows the state label', () => {
    render(<LeverBar leverKey="buyer_urgency" state="WEAK" />)
    expect(screen.getByText('WEAK')).toBeInTheDocument()
  })

  it('falls back to the key for unknown levers', () => {
    render(<LeverBar leverKey="custom_lever" state="WEAK" />)
    expect(screen.getByText('custom_lever')).toBeInTheDocument()
  })
})
