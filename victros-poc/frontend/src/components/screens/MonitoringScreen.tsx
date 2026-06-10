import { Card } from '../ui/Card'
import { Badge, severityVariant } from '../ui/Badge'
import { Button } from '../ui/Button'
import { LeverBar } from '../ui/LeverBar'
import type { Lever, Pattern, RepresentativeAction, StrategyPath } from '../../types'

interface MonitoringScreenProps {
  strategyPath: StrategyPath | null
  primaryPattern: Pattern | null
  levers: Lever[]
  leverStates: Record<string, string>
  selectedAction: RepresentativeAction | null
  onPivot: () => void
  onRestart: () => void
}

export function MonitoringScreen({
  strategyPath,
  primaryPattern,
  levers,
  leverStates,
  selectedAction,
  onPivot,
  onRestart,
}: MonitoringScreenProps) {
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-100">In progress</h2>
        <p className="text-sm text-slate-400">
          Track progress against the active strategy. Return here when the
          situation changes.
        </p>
      </div>

      {strategyPath && (
        <Card>
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Active strategy
            </p>
            <p className="text-base font-semibold text-slate-100">
              {strategyPath.display_name}
            </p>
            {strategyPath.strategic_focus && (
              <p className="text-sm text-slate-400">{strategyPath.strategic_focus}</p>
            )}
            {strategyPath.exit_outcome && (
              <div className="space-y-1">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Exit condition
                </p>
                <p className="text-sm text-slate-400">{strategyPath.exit_outcome}</p>
              </div>
            )}
            {strategyPath.positive_progress_signals.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-600">
                  Positive signals to watch
                </p>
                <ul className="space-y-0.5">
                  {strategyPath.positive_progress_signals.map((s) => (
                    <li key={s} className="text-xs text-slate-400">· {s.replace(/_/g, ' ')}</li>
                  ))}
                </ul>
              </div>
            )}
            {strategyPath.negative_progress_signals.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-semibold uppercase tracking-wider text-red-500">
                  Warning signals
                </p>
                <ul className="space-y-0.5">
                  {strategyPath.negative_progress_signals.map((s) => (
                    <li key={s} className="text-xs text-slate-400">· {s.replace(/_/g, ' ')}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}

      {selectedAction && (
        <Card>
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Selected action
            </p>
            <p className="text-sm text-slate-200">{selectedAction.ux_text}</p>
          </div>
        </Card>
      )}

      {primaryPattern && (
        <Card>
          <div className="flex items-start gap-3">
            <Badge
              label={primaryPattern.severity}
              variant={severityVariant(primaryPattern.severity)}
            />
            <div className="space-y-0.5">
              <p className="text-sm font-medium text-slate-100">{primaryPattern.name}</p>
              <p className="text-xs text-slate-400">{primaryPattern.summary}</p>
            </div>
          </div>
        </Card>
      )}

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
        <Button onClick={onPivot} variant="secondary" size="sm">
          Something changed
        </Button>
        <Button onClick={onRestart} variant="ghost" size="sm">
          New session
        </Button>
      </div>
    </div>
  )
}
