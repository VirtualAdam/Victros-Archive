import { render, screen } from '@testing-library/react'
import { Badge, severityVariant } from '../../components/ui/Badge'

describe('Badge', () => {
  it('renders its label', () => {
    render(<Badge label="HIGH" />)
    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('applies critical styles for critical variant', () => {
    render(<Badge label="CRITICAL" variant="critical" />)
    expect(screen.getByText('CRITICAL').className).toContain('red')
  })
})

describe('severityVariant', () => {
  it('maps severity strings to badge variants', () => {
    expect(severityVariant('CRITICAL')).toBe('critical')
    expect(severityVariant('HIGH')).toBe('high')
    expect(severityVariant('MEDIUM')).toBe('medium')
    expect(severityVariant('LOW')).toBe('low')
  })
})
