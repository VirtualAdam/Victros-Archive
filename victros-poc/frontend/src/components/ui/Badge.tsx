type BadgeVariant = 'critical' | 'high' | 'medium' | 'low' | 'positive' | 'neutral' | 'exit'

interface BadgeProps {
  label: string
  variant?: BadgeVariant
}

const variantClasses: Record<BadgeVariant, string> = {
  critical: 'bg-red-950 text-red-400 border-red-800',
  high:     'bg-orange-950 text-orange-400 border-orange-800',
  medium:   'bg-yellow-950 text-yellow-400 border-yellow-800',
  low:      'bg-slate-800 text-slate-400 border-slate-600',
  positive: 'bg-emerald-950 text-emerald-400 border-emerald-800',
  exit:     'bg-purple-950 text-purple-400 border-purple-800',
  neutral:  'bg-slate-800 text-slate-300 border-slate-600',
}

export function Badge({ label, variant = 'neutral' }: BadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        variantClasses[variant],
      ].join(' ')}
    >
      {label}
    </span>
  )
}

/** Map a severity string to a badge variant. */
export function severityVariant(severity: string): BadgeVariant {
  return (severity.toLowerCase() as BadgeVariant) ?? 'neutral'
}
