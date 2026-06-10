import { useState } from 'react'

interface IntentCaptureScreenProps {
  onSubmit: (text: string) => void
  loading: boolean
  isCorrection?: boolean
}

export function IntentCaptureScreen({
  onSubmit,
  loading,
  isCorrection,
}: IntentCaptureScreenProps) {
  const [text, setText] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (text.trim()) onSubmit(text.trim())
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
      <div className="w-full max-w-xl space-y-6">
        <h1 className="text-2xl font-bold text-white">
          {isCorrection
            ? 'Let me get that right — tell me more'
            : 'How can I help you win today?'}
        </h1>
        <p className="text-sm text-slate-400">
          Describe the situation in your own words. No structure needed yet.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <textarea
            className="w-full rounded-lg border border-slate-700 bg-slate-900 p-4 text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none"
            rows={5}
            placeholder="e.g. My champion went silent and I'm not sure if the deal is still alive…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="w-full rounded-lg bg-violet-600 px-4 py-3 font-medium text-white transition hover:bg-violet-500 disabled:opacity-50"
          >
            {loading ? 'Processing…' : 'Continue'}
          </button>
        </form>
      </div>
    </div>
  )
}
