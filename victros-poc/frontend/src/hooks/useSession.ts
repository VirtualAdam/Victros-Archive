import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type {
  ConfirmPatternsRequest,
  ConfirmRequest,
  DualPatternRequest,
  InputRequest,
  SelectActionRequest,
} from '../types'

const SESSION_KEY = (id: string) => ['session', id]

/**
 * Loads and keeps the session state fresh.
 * Enabled only when a sessionId is present.
 */
export function useSessionQuery(sessionId: string | null) {
  return useQuery({
    queryKey: SESSION_KEY(sessionId ?? ''),
    queryFn: () => api.getSession(sessionId!),
    enabled: !!sessionId,
    staleTime: 0,
  })
}

/**
 * All write operations against a session.
 * Each mutation invalidates the session query on success so the UI
 * always reflects the latest state from the server.
 */
export function useSessionMutations(sessionId: string | null) {
  const qc = useQueryClient()

  const invalidate = () => {
    if (sessionId) qc.invalidateQueries({ queryKey: SESSION_KEY(sessionId) })
  }

  const createSession = useMutation({
    mutationFn: api.createSession,
  })

  const submitInput = useMutation({
    mutationFn: (req: InputRequest) => api.submitInput(sessionId!, req),
    onSuccess: invalidate,
  })

  const confirm = useMutation({
    mutationFn: (req: ConfirmRequest) => api.confirm(sessionId!, req),
    onSuccess: invalidate,
  })

  const selectAction = useMutation({
    mutationFn: (req: SelectActionRequest) =>
      api.selectAction(sessionId!, req),
    onSuccess: invalidate,
  })

  const dualPattern = useMutation({
    mutationFn: (req: DualPatternRequest) =>
      api.dualPattern(sessionId!, req),
    onSuccess: invalidate,
  })

  const confirmPatterns = useMutation({
    mutationFn: (req: ConfirmPatternsRequest) =>
      api.confirmPatterns(sessionId!, req),
    onSuccess: invalidate,
  })

  const confirmUnderstanding = useMutation({
    mutationFn: (req: { response: 'confirm' | 'clarify' }) =>
      api.confirmUnderstanding(sessionId!, req),
    onSuccess: invalidate,
  })

  return { createSession, submitInput, confirm, selectAction, dualPattern, confirmPatterns, confirmUnderstanding }
}
