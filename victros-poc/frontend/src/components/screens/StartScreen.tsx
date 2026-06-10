import { useEffect, useState } from 'react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import { getAuthMe } from '../../api/client'
import { api } from '../../api/client'
import type { SessionSummary, SwaClientPrincipal } from '../../types'

interface StartScreenProps {
  onStart: (userId: string, opportunityId: string) => void
  onResume: (sessionId: string, userId: string) => void
  loading?: boolean
  error?: string | null
  authenticatedUserId?: string | null
}

function stateLabel(state: string): string {
  const map: Record<string, string> = {
    NEW_SESSION: 'New',
    INTAKE: 'Intake',
    AWAITING_CONFIRMATION: 'Reviewing signals',
    EVALUATING: 'Evaluating',
    PATTERN_DIAGNOSTICS: 'Pattern review',
    PRESENTING_DIAGNOSIS: 'Diagnosis',
    ACTION_SELECTION: 'Choosing action',
    MONITORING: 'In progress',
    RE_EVALUATING: 'Re-evaluating',
    DUAL_PATTERN_TRADEOFF: 'Pattern tradeoff',
    SESSION_COMPLETE: 'Complete',
  }
  return map[state] ?? state
}

function relativeTime(iso: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export function StartScreen({ onStart, onResume, loading, error, authenticatedUserId }: StartScreenProps) {
  const [principal, setPrincipal] = useState<SwaClientPrincipal | null | 'loading'>('loading')
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [showNewForm, setShowNewForm] = useState(false)
  const [opportunityId, setOpportunityId] = useState('')

  // Manual fallback (local dev — no auth)
  const [manualUserId, setManualUserId] = useState('')
  const [manualOpportunityId, setManualOpportunityId] = useState('')

  useEffect(() => {
    // Use SWA Easy Auth /.auth/me to get identity
    if (authenticatedUserId) {
      // Already have user ID from parent (App.tsx fetched it)
      getAuthMe().then((p) => {
        setPrincipal(p)
        setSessionsLoading(true)
        api.listSessions(authenticatedUserId)
          .then(setSessions)
          .catch(() => setSessions([]))
          .finally(() => setSessionsLoading(false))
      })
      return
    }
    // Fallback: try SWA Easy Auth directly (e.g. if parent hasn't resolved yet)
    getAuthMe().then((p) => {
      setPrincipal(p)
      if (p?.userId) {
        setSessionsLoading(true)
        api.listSessions(p.userId)
          .then(setSessions)
          .catch(() => setSessions([]))
          .finally(() => setSessionsLoading(false))
      }
    })
  }, [authenticatedUserId])

  const isAuthed = principal !== 'loading' && principal !== null

  // ── Authenticated flow ─────────────────────────────────────────────────────
  if (principal === 'loading') {
    return <Spinner label="Loading…" />
  }

  if (isAuthed) {
    const userId = (principal as SwaClientPrincipal).userId

    const handleStartNew = (e: React.FormEvent) => {
      e.preventDefault()
      if (opportunityId.trim()) {
        onStart(userId, opportunityId.trim())
      }
    }

    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-lg space-y-8">
          <div className="space-y-1 text-center">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-100">
              Victros
            </h1>
            <p className="text-sm text-slate-400">
              {(principal as SwaClientPrincipal).userDetails}
            </p>
          </div>

          {/* Existing sessions */}
          {sessionsLoading && <Spinner label="Loading your deals…" />}

          {!sessionsLoading && sessions.length > 0 && !showNewForm && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Continue a deal
              </p>
              <div className="space-y-2">
                {sessions.map((s) => (
                  <Card
                    key={s.session_id}
                    interactive
                    onClick={() => onResume(s.session_id, userId)}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-100">
                          {s.opportunity_id}
                        </p>
                        <p className="text-xs text-slate-500">
                          {relativeTime(s.updated_at)}
                        </p>
                      </div>
                      <Badge label={stateLabel(s.state)} variant="neutral" />
                    </div>
                  </Card>
                ))}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                onClick={() => setShowNewForm(true)}
              >
                + Start a new deal
              </Button>
            </div>
          )}

          {/* New deal form — shown when no sessions yet, or user chose to start new */}
          {(!sessionsLoading && (sessions.length === 0 || showNewForm)) && (
            <Card>
              <form onSubmit={handleStartNew} className="space-y-4">
                {showNewForm && (
                  <button
                    type="button"
                    className="text-xs text-slate-500 hover:text-slate-300"
                    onClick={() => setShowNewForm(false)}
                  >
                    ← Back to your deals
                  </button>
                )}
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-300">
                    Deal / Opportunity name
                  </label>
                  <input
                    value={opportunityId}
                    onChange={(e) => setOpportunityId(e.target.value)}
                    placeholder="e.g. Acme Q2 security deal"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-violet-500 focus:outline-none"
                    autoFocus
                  />
                </div>
                {error && (
                  <p className="rounded-lg bg-red-950/50 px-3 py-2 text-sm text-red-400">
                    {error}
                  </p>
                )}
                <Button
                  type="submit"
                  size="lg"
                  className="w-full"
                  loading={loading}
                  disabled={!opportunityId.trim()}
                >
                  Start session
                </Button>
              </form>
            </Card>
          )}
        </div>
      </div>
    )
  }

  // ── Local dev fallback (no SWA auth) ───────────────────────────────────────
  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (manualUserId.trim() && manualOpportunityId.trim()) {
      onStart(manualUserId.trim(), manualOpportunityId.trim())
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md space-y-8">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-100">
            Victros
          </h1>
          <p className="text-slate-400">Strategic reasoning for every deal.</p>
          <p className="text-xs text-slate-600">Local dev mode</p>
        </div>

        <Card>
          <form onSubmit={handleManualSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-300">Your ID</label>
              <input
                value={manualUserId}
                onChange={(e) => setManualUserId(e.target.value)}
                placeholder="e.g. jane_doe"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-violet-500 focus:outline-none"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-300">Opportunity</label>
              <input
                value={manualOpportunityId}
                onChange={(e) => setManualOpportunityId(e.target.value)}
                placeholder="e.g. acme_q2_security"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-violet-500 focus:outline-none"
              />
            </div>
            {error && (
              <p className="rounded-lg bg-red-950/50 px-3 py-2 text-sm text-red-400">
                {error}
              </p>
            )}
            <Button
              type="submit"
              size="lg"
              className="w-full"
              loading={loading}
              disabled={!manualUserId.trim() || !manualOpportunityId.trim()}
            >
              Start Session
            </Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
