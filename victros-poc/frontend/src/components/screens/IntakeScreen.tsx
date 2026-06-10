import { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import type { Signal } from '../../types'
import { api } from '../../api/client'

// Required fields in mandatory collection order (data-flow-logic S4)
const REQUIRED_FIELDS = [
  { key: 'deal_stage', prompt: 'What stage is this deal in?', options: ['1_Discovery', '2_Qualification', '3_Validation', '4_Negotiation'] },
  { key: 'offering_type', prompt: 'Is this a product, services, or hybrid deal?', options: ['product', 'services', 'hybrid'] },
  { key: 'offering_usage', prompt: 'Is the product already in use at this account?', options: ['yes', 'no', 'pilot', 'freemium'] },
  { key: 'usage_depth', prompt: 'How deeply is the product embedded in their workflows?', options: ['none', 'light', 'moderate', 'deep'] },
  { key: 'deal_amount', prompt: "What is the deal size?", inputType: 'text' as const },
  { key: 'deal_close_date', prompt: 'When is the expected close date?', inputType: 'text' as const },
]

interface IntakeScreenProps {
  sessionId: string
  signals: Signal[]
  onSubmitSignals: (signals: string[]) => void
  onSubmitText: (text: string) => void
  loading?: boolean
  error?: string | null
}

export function IntakeScreen({
  sessionId,
  signals,
  onSubmitSignals,
  onSubmitText: _onSubmitText,
  loading,
  error,
}: IntakeScreenProps) {
  const [phase, setPhase] = useState<'fields' | 'signals'>('fields')
  const [fieldIndex, setFieldIndex] = useState(0)
  const [textValue, setTextValue] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())

  // Check if there are still fields to collect
  useEffect(() => {
    if (sessionId) {
      api.getIntakeGaps(sessionId).then((gaps) => {
        const missing = gaps.required || []
        if (missing.length === 0) {
          // All fields collected — show signal selection
          setPhase('signals')
        } else {
          const idx = REQUIRED_FIELDS.findIndex((f) => missing.includes(f.key))
          if (idx >= 0) setFieldIndex(idx)
          setPhase('fields')
        }
      }).catch(() => {})
    }
  }, [sessionId])

  const currentField = REQUIRED_FIELDS[fieldIndex]
  const isLastField = fieldIndex >= REQUIRED_FIELDS.length - 1

  const submitField = async (value: string) => {
    setTextValue('')

    try {
      const resp = await api.submitInput(sessionId, {
        input_type: 'fields',
        fields: { [REQUIRED_FIELDS[fieldIndex].key]: value },
      })

      if (resp.next_prompt) {
        const nextIdx = REQUIRED_FIELDS.findIndex((f) => f.key === (resp.next_prompt as { field: string }).field)
        setFieldIndex(nextIdx >= 0 ? nextIdx : fieldIndex + 1)
      } else {
        setPhase('signals')
      }
    } catch {
      // If API fails, just advance locally
      if (isLastField) {
        setPhase('signals')
      } else {
        setFieldIndex(fieldIndex + 1)
      }
    }
  }

  const toggle = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const negativeSignals = signals.filter((s) => s.polarity === 'negative')
  const positiveSignals = signals.filter((s) => s.polarity === 'positive')

  // ── Phase 1: Structured field collection ──
  if (phase === 'fields' && currentField) {
    return (
      <div className="mx-auto max-w-xl space-y-6 p-6">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Step {fieldIndex + 1} of {REQUIRED_FIELDS.length}
          </p>
          <h2 className="text-xl font-semibold text-slate-100">
            {currentField.prompt}
          </h2>
        </div>

        {/* Progress dots */}
        <div className="flex gap-1.5">
          {REQUIRED_FIELDS.map((f, i) => (
            <div
              key={f.key}
              className={`h-1.5 flex-1 rounded-full ${
                i < fieldIndex
                  ? 'bg-violet-500'
                  : i === fieldIndex
                  ? 'bg-violet-400'
                  : 'bg-slate-800'
              }`}
            />
          ))}
        </div>

        {currentField.options ? (
          <div className="space-y-2">
            {currentField.options.map((opt) => (
              <button
                key={opt}
                onClick={() => submitField(opt)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-left text-sm text-slate-200 transition hover:border-violet-500 hover:bg-slate-800"
              >
                {opt.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (textValue.trim()) submitField(textValue.trim())
            }}
            className="space-y-3"
          >
            <input
              type="text"
              value={textValue}
              onChange={(e) => setTextValue(e.target.value)}
              placeholder={currentField.key === 'deal_amount' ? 'e.g. 500000' : 'e.g. 2026-06-30'}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none"
            />
            <Button type="submit" disabled={!textValue.trim()} className="w-full">
              Continue
            </Button>
          </form>
        )}
      </div>
    )
  }

  // ── Phase 2: Signal selection ──
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-100">
          Confirm deal signals
        </h2>
        <p className="text-sm text-slate-400">
          Select the conditions that reflect the current situation.
        </p>
      </div>

      <div className="space-y-4">
        <SignalGroup
          title="Structural risks"
          signals={negativeSignals}
          selected={selected}
          onToggle={toggle}
        />
        <SignalGroup
          title="Positive momentum"
          signals={positiveSignals}
          selected={selected}
          onToggle={toggle}
        />

        {error && (
          <p className="rounded-lg bg-red-950/50 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        )}

        <Button
          onClick={() => onSubmitSignals([...selected])}
          disabled={selected.size === 0}
          loading={loading}
          className="w-full"
        >
          Continue with {selected.size > 0 ? `${selected.size} signal${selected.size > 1 ? 's' : ''}` : 'selected signals'}
        </Button>
      </div>
    </div>
  )
}

function SignalGroup({
  title,
  signals,
  selected,
  onToggle,
}: {
  title: string
  signals: Signal[]
  selected: Set<string>
  onToggle: (key: string) => void
}) {
  if (signals.length === 0) return null
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        {title}
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {signals.map((s) => (
          <Card
            key={s.key}
            interactive
            selected={selected.has(s.key)}
            onClick={() => onToggle(s.key)}
          >
            <div className="space-y-1">
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm font-medium text-slate-100 leading-snug">
                  {s.name}
                </span>
                <Badge
                  label={s.severity}
                  variant={s.severity.toLowerCase() as 'critical' | 'high' | 'medium' | 'low'}
                />
              </div>
              <p className="text-xs text-slate-500 leading-snug">
                {s.observable_condition}
              </p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
