import { Card } from '../ui/Card'
import { Badge, severityVariant } from '../ui/Badge'
import { Button } from '../ui/Button'
import { LeverBar } from '../ui/LeverBar'
import type { Lever, Pattern, RepresentativeAction, StrategyPath } from '../../types'

interface DiagnosisScreenProps {
  primaryPattern: Pattern | null
  secondaryPatterns: Pattern[]
  strategyPath: StrategyPath | null
  actions: RepresentativeAction[]
  levers: Lever[]
  leverStates: Record<string, string>
  onSelectAction: (actionKey: string) => void
  onPivot: () => void
  loading?: boolean
}

export function DiagnosisScreen({
  primaryPattern,
  secondaryPatterns,
  strategyPath,
  actions,
  levers,
  leverStates,
  onSelectAction,
  onPivot,
  loading,
}: DiagnosisScreenProps) {
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      {/* Structural implication first — per Richard's spec */}
      {strategyPath && (
        <div className="space-y-1">
          <h2 className="text-xl font-semibold text-slate-100">
            {strategyPath.display_name}
          </h2>
          <p className="text-sm text-slate-400">{strategyPath.description}</p>
        </div>
      )}

      {/* Risk explanation */}
      {primaryPattern && (
        <Card>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Badge
                label={primaryPattern.severity}
                variant={severityVariant(primaryPattern.severity)}
              />
              {primaryPattern.resolution_type === 'EXIT' && (
                <Badge label="EXIT" variant="exit" />
              )}
              <span className="text-xs text-slate-500">Primary condition</span>
            </div>
            <p className="text-sm font-medium text-slate-100">
              {primaryPattern.name}
            </p>
            <p className="text-sm text-slate-400 leading-relaxed">
              {primaryPattern.summary}
            </p>
            {primaryPattern.diagnostic_questions.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Diagnostic questions
                </p>
                <ul className="space-y-1">
                  {primaryPattern.diagnostic_questions.slice(0, 3).map((q, i) => (
                    <li key={i} className="text-xs text-slate-400">· {q}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Secondary patterns */}
      {secondaryPatterns.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Also present
          </p>
          <div className="flex flex-wrap gap-2">
            {secondaryPatterns.map((p) => (
              <Badge key={p.key} label={p.name} variant={severityVariant(p.severity)} />
            ))}
          </div>
        </div>
      )}

      {/* Representative actions — real ux_text from schema */}
      {actions.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Next moves
          </p>
          <div className="grid gap-2">
            {actions.map((action) => (
              <Card
                key={action.action_key}
                interactive
                onClick={() => onSelectAction(action.action_key)}
              >
                <p className="text-sm text-slate-200 leading-snug">
                  {action.ux_text}
                </p>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Lever states — real names from schema */}
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Structural health
        </p>
        <Card>
          <div className="space-y-3">
            {Object.entries(leverStates).map(([key, state]) => {
              const lever = levers.find((l) => l.key === key)
              return (
                <LeverBar
                  key={key}
                  leverKey={key}
                  leverName={lever?.name}
                  state={state}
                  whyItMatters={lever?.why_it_matters}
                />
              )
            })}
          </div>
        </Card>
      </div>

      <div className="flex gap-2 border-t border-slate-800 pt-4">
        <Button variant="ghost" size="sm" onClick={onPivot} disabled={loading}>
          Something changed
        </Button>
      </div>
    </div>
  )
}
