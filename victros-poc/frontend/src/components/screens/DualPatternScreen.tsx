import { Card } from '../ui/Card'
import type { Pattern } from '../../types'

const OPTIONS = [
  {
    choice: 'focus' as const,
    label: 'Focus on priority',
    description: 'Fix the primary structural risk first before anything else.',
    risk: 'May slow visible progress.',
    best: 'Fragile deals.',
  },
  {
    choice: 'combine' as const,
    label: 'Combine both motions',
    description: 'Use the current strategy to also address the secondary risk.',
    risk: 'Can dilute clarity if forced.',
    best: 'When moves naturally overlap.',
  },
  {
    choice: 'sequence' as const,
    label: 'Sequence it',
    description: 'Make progress on the primary, then return to the secondary.',
    risk: 'Secondary issue may worsen.',
    best: 'Maintaining momentum.',
  },
]

interface DualPatternScreenProps {
  primaryPattern: Pattern | null
  secondaryPattern: Pattern | null
  onChoice: (choice: 'focus' | 'combine' | 'sequence') => void
  loading?: boolean
}

export function DualPatternScreen({
  primaryPattern,
  secondaryPattern,
  onChoice,
  loading,
}: DualPatternScreenProps) {
  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-100">
          Two structural risks are active.
        </h2>
        <p className="text-sm text-slate-400">
          One is more critical — but the other still matters. How do you want
          to proceed?
        </p>
      </div>

      {primaryPattern && secondaryPattern && (
        <Card>
          <div className="space-y-3">
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Priority
              </p>
              <p className="text-sm font-medium text-slate-100">
                {primaryPattern.name}
              </p>
              <p className="text-xs text-slate-400">{primaryPattern.summary}</p>
            </div>
            <div className="space-y-1 border-t border-slate-700 pt-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Secondary
              </p>
              <p className="text-sm font-medium text-slate-200">
                {secondaryPattern.name}
              </p>
              <p className="text-xs text-slate-400">{secondaryPattern.summary}</p>
            </div>
          </div>
        </Card>
      )}

      <div className="space-y-2">
        {OPTIONS.map((opt) => (
          <Card key={opt.choice} interactive onClick={() => !loading && onChoice(opt.choice)}>
            <div className="space-y-1.5">
              <p className="text-sm font-semibold text-slate-100">{opt.label}</p>
              <p className="text-xs text-slate-400">{opt.description}</p>
              <div className="flex gap-4 text-xs text-slate-500">
                <span>Best for: {opt.best}</span>
                <span>Risk: {opt.risk}</span>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {loading && (
        <p className="text-center text-sm text-slate-500">Processing…</p>
      )}
    </div>
  )
}
