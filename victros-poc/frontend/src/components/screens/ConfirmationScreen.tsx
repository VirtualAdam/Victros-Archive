import { useState } from 'react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'

interface ProposalItem {
  label: string
  value: string
}

interface ConfirmationScreenProps {
  proposal: {
    signals: ProposalItem[]
    deal_attributes: ProposalItem[]
    summary: string
  }
  onConfirm: (dealStage: string) => void
  onAdjust: () => void
  onReject: () => void
  loading?: boolean
}

const DEAL_STAGES = [
  { key: 'zone1', label: 'Early Stage', sub: 'Discovery / Pre-Qualification' },
  { key: 'zone2', label: 'Evaluation', sub: 'Qualification' },
  { key: 'zone3', label: 'Mid-Stage', sub: 'Consensus / Validation' },
  { key: 'zone4', label: 'Late Stage', sub: 'Negotiation / Close' },
]

export function ConfirmationScreen({
  proposal,
  onConfirm,
  onAdjust,
  onReject,
  loading,
}: ConfirmationScreenProps) {
  const [dealStage, setDealStage] = useState('')

  const hasStage = proposal.deal_attributes.some(
    (a) => a.label.toLowerCase().includes('stage'),
  )

  const stageFromProposal = proposal.deal_attributes.find(
    (a) => a.label.toLowerCase().includes('stage'),
  )?.value ?? ''

  const effectiveStage = stageFromProposal || dealStage

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-100">
          Here's what I'm seeing.
        </h2>
        <p className="text-sm text-slate-400">
          Review the situation before we run the analysis.
        </p>
      </div>

      <Card>
        <div className="space-y-4">
          {proposal.signals.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Signals detected
              </p>
              <ul className="space-y-1">
                {proposal.signals.map((s) => (
                  <li key={s.value} className="flex items-center gap-2 text-sm text-slate-200">
                    <span className="size-1.5 shrink-0 rounded-full bg-violet-400" />
                    {s.label}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {proposal.deal_attributes.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Deal context
              </p>
              <ul className="space-y-1">
                {proposal.deal_attributes.map((a) => (
                  <li key={a.label} className="flex gap-2 text-sm">
                    <span className="text-slate-500">{a.label}:</span>
                    <span className="text-slate-200">{a.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </Card>

      {!hasStage && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-300">
            Where is this deal?{' '}
            <span className="text-slate-500 font-normal">(required to proceed)</span>
          </p>
          <div className="grid grid-cols-2 gap-2">
            {DEAL_STAGES.map((stage) => (
              <Card
                key={stage.key}
                interactive
                selected={dealStage === stage.key}
                onClick={() => setDealStage(stage.key)}
              >
                <p className="text-sm font-medium text-slate-100">{stage.label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{stage.sub}</p>
              </Card>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        <Button
          className="flex-1"
          onClick={() => onConfirm(effectiveStage)}
          loading={loading}
          disabled={!hasStage && !dealStage}
        >
          Yes, that's right
        </Button>
        <Button variant="secondary" onClick={onAdjust} disabled={loading}>
          Adjust
        </Button>
        <Button variant="ghost" onClick={onReject} disabled={loading}>
          Not correct
        </Button>
      </div>
    </div>
  )
}
