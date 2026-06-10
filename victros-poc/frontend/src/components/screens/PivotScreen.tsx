import { useState } from 'react'
import { Button } from '../ui/Button'

interface PivotScreenProps {
  onSubmit: (text: string) => void
  onCancel: () => void
  loading?: boolean
}

export function PivotScreen({ onSubmit, onCancel, loading }: PivotScreenProps) {
  const [text, setText] = useState('')

  const PIVOT_EXAMPLES = [
    "Champion is back and actively pushing the deal. Budget approval came through.",
    "A new VP of security was just introduced. Nobody told us about them before.",
    "We lost access to the EB. New procurement process requires a three vendor eval.",
    "Competitor just got a follow-up meeting. Our champion couldn't get us on the agenda.",
  ]

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-100">
          What changed?
        </h2>
        <p className="text-sm text-slate-400">
          Describe the new situation. Victros will extract any structural
          changes and confirm them with you before updating the analysis.
        </p>
      </div>

      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Try an example
        </p>
        <div className="flex flex-col gap-1.5">
          {PIVOT_EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => setText(ex)}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-left text-xs text-slate-400 hover:border-violet-500 hover:text-slate-200 transition-colors cursor-pointer"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Describe what changed…"
        rows={4}
        autoFocus
        className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-violet-500 focus:outline-none resize-none"
      />

      <div className="flex gap-2">
        <Button
          onClick={() => onSubmit(text)}
          disabled={text.trim().length < 5}
          loading={loading}
          className="flex-1"
        >
          Analyze update
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
