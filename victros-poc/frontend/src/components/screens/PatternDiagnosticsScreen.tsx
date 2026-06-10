import { Badge, severityVariant } from '../ui/Badge'
import { Button } from '../ui/Button'
import type { Pattern } from '../../types'

interface PatternDiagnosticsScreenProps {
  /** Engine-activated patterns, already sorted CRITICAL first. */
  patterns: Pattern[]
  metaExplanation: string
  onConfirm: (selectedKeys: string[]) => void
  onRejectAll: () => void
  loading?: boolean
}

export function PatternDiagnosticsScreen({
  patterns,
  metaExplanation,
  onConfirm,
  onRejectAll,
  loading,
}: PatternDiagnosticsScreenProps) {
  const allKeys = patterns.map((p) => p.key)

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-100">
          Structural Diagnosis
        </h2>
        <p className="text-sm text-slate-400 leading-relaxed">
          {metaExplanation ||
            "Based on the confirmed signals, the system identified the following structural condition. Does this match what you\u2019re seeing?"}
        </p>
      </div>

      <div className="space-y-3">
        {patterns.map((pattern, i) => (
          <div
            key={pattern.key}
            className="w-full rounded-xl border border-violet-500 bg-slate-900 p-4 text-left"
          >
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Badge
                  label={pattern.severity}
                  variant={severityVariant(pattern.severity)}
                />
                <Badge
                  label={pattern.resolution_type}
                  variant={
                    pattern.resolution_type === 'EXIT'
                      ? 'exit'
                      : pattern.resolution_type === 'ADVANCE'
                      ? 'positive'
                      : 'neutral'
                  }
                />
                <span className="text-xs font-medium text-slate-400">
                  {i === 0 ? 'Primary' : 'Secondary'}
                </span>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-100">
                  {pattern.name}
                </p>
                <p className="mt-1 text-sm text-slate-400 leading-relaxed">
                  {pattern.summary}
                </p>
              </div>

              {pattern.diagnostic_questions.length > 0 && (
                <div className="space-y-1 border-t border-slate-800 pt-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Diagnostic questions
                  </p>
                  <ul className="space-y-1">
                    {pattern.diagnostic_questions.map((q, qi) => (
                      <li key={qi} className="text-xs text-slate-400">
                        · {q}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-2 border-t border-slate-800 pt-4">
        <div className="flex gap-3">
          <Button
            size="lg"
            className="flex-1"
            onClick={() => onConfirm(allKeys)}
            loading={loading}
          >
            Yes, this matches what I'm seeing
          </Button>
          <Button
            variant="ghost"
            size="lg"
            onClick={onRejectAll}
            disabled={loading}
          >
            No, this doesn't reflect the situation
          </Button>
        </div>
      </div>
    </div>
  )
}
