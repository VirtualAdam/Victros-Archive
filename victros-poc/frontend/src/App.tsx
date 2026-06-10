import { useState, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useSessionQuery,
  useSessionMutations,
} from './hooks/useSession'
import {
  useActionsByStrategyPath,
  useLevers,
  usePatternByKey,
  usePatterns,
  useRepresentativeActions,
  useSignals,
  useStrategyPathByKey,
} from './hooks/useSchema'
import { Spinner } from './components/ui/Spinner'
import { StartScreen } from './components/screens/StartScreen'
import { IntentCaptureScreen } from './components/screens/IntentCaptureScreen'
import { SituationValidationScreen } from './components/screens/SituationValidationScreen'
import { IntakeScreen } from './components/screens/IntakeScreen'
import { ConfirmationScreen } from './components/screens/ConfirmationScreen'
import { PatternDiagnosticsScreen } from './components/screens/PatternDiagnosticsScreen'
import { DiagnosisScreen } from './components/screens/DiagnosisScreen'
import { DualPatternScreen } from './components/screens/DualPatternScreen'
import { MonitoringScreen } from './components/screens/MonitoringScreen'
import { PivotScreen } from './components/screens/PivotScreen'
import { getAuthMe } from './api/client'
import type { ConfirmationProposal } from './types'

const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3,
}

/** Convert the backend's { items: [...] } shape into the ConfirmationScreen props shape. */
function normalizeProposal(raw: Record<string, unknown>): ConfirmationProposal {
  const items = (raw.items ?? []) as Array<Record<string, unknown>>
  const signals = items
    .filter((i) => i.signal && i.action === 'add')
    .map((i) => ({ label: String(i.signal).replace(/_/g, ' '), value: String(i.signal) }))
  const deal_attributes = items
    .filter((i) => i.attribute)
    .map((i) => ({ label: String(i.attribute), value: String(i.value) }))
  return { signals, deal_attributes, summary: '' }
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const [inputError, setInputError] = useState<string | null>(null)
  const [isPivoting, setIsPivoting] = useState(false)
  const [lastProposal, setLastProposal] = useState<ConfirmationProposal | null>(null)
  const [selectedActionKey, setSelectedActionKey] = useState<string | null>(null)
  const [patternMetaExplanation, setPatternMetaExplanation] = useState('')
  const [situationSummary, setSituationSummary] = useState('')
  const [isCorrection, setIsCorrection] = useState(false)

  // Get authenticated user from SWA Easy Auth
  const [authenticatedUserId, setAuthenticatedUserId] = useState<string | null>(null)
  useEffect(() => {
    getAuthMe().then((p) => {
      if (p?.userId) setAuthenticatedUserId(p.userId)
    })
  }, [])

  const qc = useQueryClient()
  const { data: session, isLoading: sessionLoading } = useSessionQuery(sessionId)
  const mutations = useSessionMutations(sessionId)

  // Schema data (cached, shared)
  const { data: signals = [] } = useSignals()
  const { data: patterns = [] } = usePatterns()
  const { data: levers = [] } = useLevers()
  const { data: allActions = [] } = useRepresentativeActions()
  const primaryPattern = usePatternByKey(session?.active_patterns.primary ?? null)
  const secondaryPatterns = patterns.filter((p) =>
    session?.active_patterns.secondary.includes(p.key),
  )
  const strategyPath = useStrategyPathByKey(session?.selected_strategy_path ?? null)
  const strategyPathActions = useActionsByStrategyPath(session?.selected_strategy_path ?? null)

  // ── Start a new session ───────────────────────────────────────────────────
  const handleStart = async (userId: string, opportunityId: string) => {
    setStartError(null)
    try {
      const newSession = await mutations.createSession.mutateAsync({
        user_id: userId,
        opportunity_id: opportunityId,
      })
      setSessionId(newSession.session_id)
      qc.setQueryData(['session', newSession.session_id], newSession)
    } catch (e) {
      setStartError(e instanceof Error ? e.message : 'Failed to create session')
    }
  }

  // ── Resume an existing session ────────────────────────────────────────────
  const handleResume = (resumeSessionId: string, _userId: string) => {
    setSessionId(resumeSessionId)
  }

  // ── Submit intent text (INTENT_CAPTURE) ─────────────────────────────────
  const handleIntentSubmit = async (text: string) => {
    setInputError(null)
    try {
      const res = await mutations.submitInput.mutateAsync({
        input_type: 'text',
        content: text,
      })
      if (res.situation_summary) {
        setSituationSummary(res.situation_summary as string)
      }
      setIsCorrection(false)
    } catch (e) {
      setInputError(e instanceof Error ? e.message : 'Failed to capture intent')
    }
  }

  // ── Confirm situation (SITUATION_VALIDATION) ────────────────────────────
  const handleSituationConfirm = async () => {
    try {
      await mutations.confirm.mutateAsync({ response: 'confirm' })
    } catch (e) {
      setInputError(e instanceof Error ? e.message : 'Failed to confirm situation')
    }
  }

  const handleSituationCorrect = async () => {
    try {
      await mutations.confirm.mutateAsync({ response: 'correct' })
      setIsCorrection(true)
    } catch (e) {
      setInputError(e instanceof Error ? e.message : 'Failed to correct situation')
    }
  }

  // ── Submit intake signals (button mode) ───────────────────────────────────
  const handleSubmitSignals = async (signalKeys: string[]) => {
    setInputError(null)
    try {
      const res = await mutations.submitInput.mutateAsync({
        input_type: 'button',
        signals: signalKeys,
      })
      if (res.proposal) setLastProposal(normalizeProposal(res.proposal as Record<string, unknown>))
    } catch (e) {
      setInputError(e instanceof Error ? e.message : 'Submission failed')
    }
  }

  // ── Submit intake text (text mode) ───────────────────────────────────────
  const handleSubmitText = async (text: string) => {
    setInputError(null)
    try {
      const res = await mutations.submitInput.mutateAsync({
        input_type: 'text',
        content: text,
      })
      if (res.proposal) setLastProposal(normalizeProposal(res.proposal as Record<string, unknown>))
      else setInputError('No signals found. Try selecting signals manually.')
    } catch (e) {
      setInputError(e instanceof Error ? e.message : 'Submission failed')
    }
  }

  // ── Confirm signal proposal → lands at PATTERN_DIAGNOSTICS ───────────────
  const handleConfirm = async (dealStage: string) => {
    const res = await mutations.confirm.mutateAsync({
      response: 'confirm',
      deal_stage: dealStage || undefined,
    })
    setLastProposal(null)
    // Capture meta-explanation from the pattern group response
    if (res && typeof res === 'object' && 'pattern_group' in res) {
      const pg = res.pattern_group as Record<string, unknown> | undefined
      setPatternMetaExplanation(String(pg?.meta_explanation ?? ''))
    }
  }

  // ── Confirm pattern group ────────────────────────────────────────────────
  const handleConfirmPatterns = async (selectedKeys: string[]) => {
    const activatedKeys = [
      ...(session?.active_patterns.primary ? [session.active_patterns.primary] : []),
      ...(session?.active_patterns.secondary ?? []),
    ]
    const response =
      selectedKeys.length === activatedKeys.length ? 'confirm_all' : 'confirm_subset'
    await mutations.confirmPatterns.mutateAsync({
      response,
      confirmed_keys: response === 'confirm_subset' ? selectedKeys : undefined,
    })
  }

  const handleRejectAllPatterns = async () => {
    await mutations.confirmPatterns.mutateAsync({ response: 'reject_all' })
  }

  // ── Select an action ──────────────────────────────────────────────────────
  const handleSelectAction = async (actionKey: string) => {
    await mutations.selectAction.mutateAsync({ action_key: actionKey })
    setSelectedActionKey(actionKey)
  }

  // ── Dual pattern choice ───────────────────────────────────────────────────
  const handleDualPatternChoice = async (
    choice: 'focus' | 'combine' | 'sequence',
  ) => {
    await mutations.dualPattern.mutateAsync({ choice })
  }

  // ── Pivot ─────────────────────────────────────────────────────────────────
  const handlePivotSubmit = async (text: string) => {
    setInputError(null)
    setIsPivoting(false)
    try {
      const res = await mutations.submitInput.mutateAsync({
        input_type: 'text',
        content: text,
      })
      if (res.proposal) setLastProposal(normalizeProposal(res.proposal as Record<string, unknown>))
    } catch (e) {
      setInputError(e instanceof Error ? e.message : 'Pivot failed')
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleRestart = () => {
    setSessionId(null)
    setLastProposal(null)
    setSelectedActionKey(null)
    setIsPivoting(false)
    setInputError(null)
    setPatternMetaExplanation('')
    setSituationSummary('')
    setIsCorrection(false)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (!sessionId) {
    return (
      <StartScreen
        onStart={handleStart}
        onResume={handleResume}
        loading={mutations.createSession.isPending}
        error={startError}
        authenticatedUserId={authenticatedUserId}
      />
    )
  }

  if (sessionLoading) {
    return <Spinner label="Loading session…" />
  }

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-slate-400">Session not found.</p>
      </div>
    )
  }

  if (isPivoting) {
    return (
      <PivotScreen
        onSubmit={handlePivotSubmit}
        onCancel={() => setIsPivoting(false)}
        loading={mutations.submitInput.isPending}
      />
    )
  }

  const state = session.state

  // ── S2: INTENT_CAPTURE ──────────────────────────────────────────────────
  if (state === 'INTENT_CAPTURE' || state === 'NEW_SESSION') {
    return (
      <IntentCaptureScreen
        onSubmit={handleIntentSubmit}
        loading={mutations.submitInput.isPending}
        isCorrection={isCorrection}
      />
    )
  }

  // ── S3: SITUATION_VALIDATION ────────────────────────────────────────────
  if (state === 'SITUATION_VALIDATION') {
    return (
      <SituationValidationScreen
        summary={situationSummary || session.intent_text || ''}
        onConfirm={handleSituationConfirm}
        onCorrect={handleSituationCorrect}
        loading={mutations.confirm.isPending}
      />
    )
  }

  // ── S4: INTAKE ──────────────────────────────────────────────────────────
  if (state === 'INTAKE') {
    return (
      <IntakeScreen
        sessionId={sessionId!}
        signals={signals}
        onSubmitSignals={handleSubmitSignals}
        onSubmitText={handleSubmitText}
        loading={mutations.submitInput.isPending}
        error={inputError}
      />
    )
  }

  if (state === 'AWAITING_CONFIRMATION' && lastProposal) {
    return (
      <ConfirmationScreen
        proposal={lastProposal}
        onConfirm={handleConfirm}
        onAdjust={() => mutations.confirm.mutate({ response: 'adjust' })}
        onReject={() => mutations.confirm.mutate({ response: 'reject' })}
        loading={mutations.confirm.isPending}
      />
    )
  }

  // ── Pattern diagnostics — the user validates the activated pattern group ──
  if (state === 'PATTERN_DIAGNOSTICS') {
    // Derive activated patterns from session (works on page refresh too)
    const activatedKeys = [
      ...(session.active_patterns.primary ? [session.active_patterns.primary] : []),
      ...session.active_patterns.secondary,
    ]
    const activatedPatterns = patterns
      .filter((p) => activatedKeys.includes(p.key))
      .sort((a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9))

    return (
      <PatternDiagnosticsScreen
        patterns={activatedPatterns}
        metaExplanation={patternMetaExplanation}
        onConfirm={handleConfirmPatterns}
        onRejectAll={handleRejectAllPatterns}
        loading={mutations.confirmPatterns.isPending}
      />
    )
  }

  if (state === 'DUAL_PATTERN_TRADEOFF') {
    return (
      <DualPatternScreen
        primaryPattern={primaryPattern}
        secondaryPattern={secondaryPatterns[0] ?? null}
        onChoice={handleDualPatternChoice}
        loading={mutations.dualPattern.isPending}
      />
    )
  }

  if (state === 'ALIGNMENT_CHECKPOINT') {
    return (
      <DiagnosisScreen
        primaryPattern={primaryPattern}
        secondaryPatterns={secondaryPatterns}
        strategyPath={strategyPath}
        actions={strategyPathActions}
        levers={levers}
        leverStates={session.lever_states}
        onSelectAction={handleSelectAction}
        onPivot={() => setIsPivoting(true)}
        loading={mutations.selectAction.isPending}
      />
    )
  }

  if (state === 'PRESENTING_DIAGNOSIS' || state === 'ACTION_SELECTION') {
    return (
      <DiagnosisScreen
        primaryPattern={primaryPattern}
        secondaryPatterns={secondaryPatterns}
        strategyPath={strategyPath}
        actions={strategyPathActions}
        levers={levers}
        leverStates={session.lever_states}
        onSelectAction={handleSelectAction}
        onPivot={() => setIsPivoting(true)}
        loading={mutations.selectAction.isPending}
      />
    )
  }

  if (state === 'SESSION_PAUSED') {
    const effectiveActionKey = selectedActionKey ?? session.selected_action_key ?? null
    const selectedAction = allActions.find((a) => a.action_key === effectiveActionKey) ?? null
    return (
      <MonitoringScreen
        strategyPath={strategyPath}
        primaryPattern={primaryPattern}
        levers={levers}
        leverStates={session.lever_states}
        selectedAction={selectedAction}
        onPivot={() => setIsPivoting(true)}
        onRestart={handleRestart}
      />
    )
  }

  if (state === 'MONITORING' || state === 'RE_EVALUATING') {
    const effectiveActionKey = selectedActionKey ?? session.selected_action_key ?? null
    const selectedAction = allActions.find((a) => a.action_key === effectiveActionKey) ?? null
    return (
      <MonitoringScreen
        strategyPath={strategyPath}
        primaryPattern={primaryPattern}
        levers={levers}
        leverStates={session.lever_states}
        selectedAction={selectedAction}
        onPivot={() => setIsPivoting(true)}
        onRestart={handleRestart}
      />
    )
  }

  if (state === 'SESSION_COMPLETE') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
        <div className="mx-auto max-w-xl space-y-6 text-center">
          <div className="text-4xl">&#10003;</div>
          <h1 className="text-2xl font-bold text-white">Session Complete</h1>
          <p className="text-slate-400">
            The strategy path has been resolved. You can start a new deal
            or return to review your session history.
          </p>
          <button
            onClick={handleRestart}
            className="rounded-lg bg-violet-600 px-6 py-3 font-medium text-white transition hover:bg-violet-500"
          >
            Start New Deal
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-slate-400">
        Unknown state:{' '}
        <code className="text-violet-400">{state}</code>
      </p>
    </div>
  )
}
