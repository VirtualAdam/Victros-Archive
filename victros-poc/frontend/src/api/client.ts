/**
 * Typed API client — one function per backend endpoint.
 * All requests go through the Vite proxy → http://localhost:8000
 */
import type {
  ActionItem,
  ConfirmPatternsRequest,
  ConfirmPatternsResponse,
  ConfirmRequest,
  CreateSessionRequest,
  DiagnosisResponse,
  DualPatternRequest,
  GeneralAssistResponse,
  InputRequest,
  InputResponse,
  Lever,
  Pattern,
  RepresentativeAction,
  SalesZone,
  SelectActionRequest,
  SessionState,
  SessionSummary,
  Signal,
  StrategyPath,
  SwaClientPrincipal,
} from '../types'

const BASE = '/api'

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json() as Promise<T>
}

// ─── Auth (SWA) ───────────────────────────────────────────────────────────────

/** Returns the authenticated user from SWA Easy Auth, or null in local dev. */
export async function getAuthMe(): Promise<SwaClientPrincipal | null> {
  try {
    const res = await fetch('/.auth/me', { credentials: 'include' })
    if (!res.ok) return null
    const data = await res.json()
    return data?.clientPrincipal ?? null
  } catch {
    return null
  }
}

// ─── Session ──────────────────────────────────────────────────────────────────

export const api = {
  createSession(req: CreateSessionRequest): Promise<SessionState> {
    return request(`${BASE}/session/create`, {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  getSession(sessionId: string): Promise<SessionState> {
    return request(`${BASE}/session/${sessionId}`)
  },

  deleteSession(sessionId: string): Promise<void> {
    return request(`${BASE}/session/${sessionId}`, { method: 'DELETE' })
  },

  listSessions(userId: string): Promise<SessionSummary[]> {
    return request(`${BASE}/sessions?user_id=${encodeURIComponent(userId)}`)
  },

  getIntakeGaps(sessionId: string): Promise<{ required: string[]; has_signals: boolean }> {
    return request(`${BASE}/session/${sessionId}/intake-gaps`)
  },

  // ─── Input / Confirm / Pivot ─────────────────────────────────────────────

  submitInput(sessionId: string, req: InputRequest): Promise<InputResponse> {
    return request(`${BASE}/session/${sessionId}/input`, {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  confirm(
    sessionId: string,
    req: ConfirmRequest,
  ): Promise<DiagnosisResponse | { state: string; missing?: string[] }> {
    return request(`${BASE}/session/${sessionId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  selectAction(
    sessionId: string,
    req: SelectActionRequest,
  ): Promise<{ state: string; action_key: string }> {
    return request(`${BASE}/session/${sessionId}/select-action`, {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  dualPattern(
    sessionId: string,
    req: DualPatternRequest,
  ): Promise<{ state: string; choice: string }> {
    return request(`${BASE}/session/${sessionId}/dual-pattern`, {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  // ─── Pattern diagnostics ──────────────────────────────────────────────────

  confirmPatterns(
    sessionId: string,
    req: ConfirmPatternsRequest,
  ): Promise<ConfirmPatternsResponse> {
    return request(`${BASE}/session/${sessionId}/confirm-patterns`, {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  confirmUnderstanding(
    sessionId: string,
    req: { response: 'confirm' | 'clarify' },
  ): Promise<{ state: string; representative_actions?: ActionItem[] }> {
    return request(`${BASE}/session/${sessionId}/confirm-understanding`, {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  // ─── General assist ───────────────────────────────────────────────────────

  generalAssist(content: string): Promise<GeneralAssistResponse> {
    return request(`${BASE}/general-assist`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    })
  },

  // ─── Schema ───────────────────────────────────────────────────────────────

  getSignals(): Promise<Signal[]> {
    return request(`${BASE}/schema/signals`)
  },

  getPatterns(): Promise<Pattern[]> {
    return request(`${BASE}/schema/patterns`)
  },

  getStrategyPaths(): Promise<StrategyPath[]> {
    return request(`${BASE}/schema/strategy-paths`)
  },

  getLevers(): Promise<Lever[]> {
    return request(`${BASE}/schema/levers`)
  },

  getSalesZones(): Promise<SalesZone[]> {
    return request(`${BASE}/schema/sales-zones`)
  },

  getRepresentativeActions(): Promise<RepresentativeAction[]> {
    return request(`${BASE}/schema/representative-actions`)
  },
}
