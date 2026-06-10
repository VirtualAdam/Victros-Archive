interface SituationValidationScreenProps {
  summary: string
  onConfirm: () => void
  onCorrect: () => void
  loading: boolean
}

export function SituationValidationScreen({
  summary,
  onConfirm,
  onCorrect,
  loading,
}: SituationValidationScreenProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
      <div className="w-full max-w-xl space-y-6">
        <h1 className="text-2xl font-bold text-white">
          {"Here\u2019s what I\u2019m hearing"}
        </h1>
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <p className="text-slate-300">{summary}</p>
        </div>
        <p className="text-sm text-slate-400">
          Does this capture the situation? I want to make sure I understand
          before we dig into the details.
        </p>
        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 rounded-lg bg-violet-600 px-4 py-3 font-medium text-white transition hover:bg-violet-500 disabled:opacity-50"
          >
            {loading ? "Processing\u2026" : "Yes, that\u2019s right"}
          </button>
          <button
            onClick={onCorrect}
            disabled={loading}
            className="flex-1 rounded-lg border border-slate-600 px-4 py-3 font-medium text-slate-300 transition hover:bg-slate-800 disabled:opacity-50"
          >
            Let me clarify
          </button>
        </div>
      </div>
    </div>
  )
}
