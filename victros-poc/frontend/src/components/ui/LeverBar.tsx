// Fallback labels if schema hasn't loaded yet
const LEVER_LABELS: Record<string, string> = {
  case_for_change_strength: 'Case for Change',
  champion_strength: 'Champion Strength',
  economic_buyer_commitment: 'Economic Buyer',
  buyer_consensus: 'Buyer Consensus',
  decision_process_alignment: 'Decision Process',
  differentiation_leverage: 'Differentiation',
  buyer_urgency: 'Buyer Urgency',
}

const STATE_WIDTH: Record<string, string> = {
  WEAK:      'w-1/4',
  CONNECTED: 'w-2/4',
  COMMITTED: 'w-3/4',
  EXECUTING: 'w-full',
}

const STATE_COLOR: Record<string, string> = {
  WEAK:      'bg-slate-600',
  CONNECTED: 'bg-violet-500',
  COMMITTED: 'bg-emerald-500',
  EXECUTING: 'bg-teal-400',
}

interface LeverBarProps {
  leverKey: string
  state: string
  leverName?: string       // real name from schema (overrides fallback)
  whyItMatters?: string    // shown as tooltip title
}

export function LeverBar({ leverKey, state, leverName, whyItMatters }: LeverBarProps) {
  const label = leverName ?? LEVER_LABELS[leverKey] ?? leverKey
  return (
    <div className="space-y-1" title={whyItMatters}>
      <div className="flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span className="font-mono uppercase text-slate-500">{state}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-800">
        <div
          className={[
            'h-full rounded-full transition-all duration-500',
            STATE_WIDTH[state] ?? 'w-1/4',
            STATE_COLOR[state] ?? 'bg-slate-600',
          ].join(' ')}
        />
      </div>
    </div>
  )
}
