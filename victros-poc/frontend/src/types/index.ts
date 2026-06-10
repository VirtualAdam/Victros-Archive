// ─── Schema entities ─────────────────────────────────────────────────────────

export interface Signal {
  key: string
  name: string
  description: string
  observable_condition: string
  polarity: 'positive' | 'negative'
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  type: 'structural_risk' | 'momentum_risk' | 'structural_strength' | 'momentum_strength'
  affected_levers: string[]
  zone_bias: string[]
  target_patterns: string[]
}

export interface Pattern {
  key: string
  name: string
  description: string
  summary: string
  trigger_signals: string[]
  diagnostic_questions: string[]
  root_cause_themes: string[]
  polarity: string
  type: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  resolution_type: 'RECOVER' | 'ADVANCE' | 'EXIT'
  zone_bias: string[]
  affected_levers: string[]
  candidate_strategy_path_keys: string[]
}

export interface StrategyPath {
  key: string
  display_name: string
  description: string
  mode: 'RECOVER' | 'ADVANCE' | 'EXIT'
  diagnostic_question: string
  target_levers: string[]
  zone_bias: string[]
  entry_conditions: string[]
  disqualifying_conditions: string[]
  core_objectives: string
  strategic_focus: string
  core_strategies: string[]
  representative_actions: string[]
  positive_progress_signals: string[]
  negative_progress_signals: string[]
  exit_lever_state: string
  exit_outcome: string
}

export interface Lever {
  key: string
  name: string
  qualifiers: string
  score_model: string
  lever_scoring: string
  why_it_matters: string
  states: string[]
}

export interface SalesZone {
  key: string
  display_name: string
  buyer_type: string
  purpose: string
  core_objectives: string
  qualification_requirements: string[]
}

export interface RepresentativeAction {
  action_key: string
  parent_strategy_path: string
  description: string
  ux_text: string
}

// ─── Session state machine ────────────────────────────────────────────────────

export type SessionStateName =
  | 'NEW_SESSION'
  | 'INTENT_CAPTURE'
  | 'SITUATION_VALIDATION'
  | 'INTAKE'
  | 'AWAITING_CONFIRMATION'
  | 'EVALUATING'
  | 'PATTERN_DIAGNOSTICS'
  | 'PRESENTING_DIAGNOSIS'
  | 'DUAL_PATTERN_TRADEOFF'
  | 'ACTION_SELECTION'
  | 'MONITORING'
  | 'RE_EVALUATING'
  | 'ALIGNMENT_CHECKPOINT'
  | 'SESSION_PAUSED'
  | 'SESSION_COMPLETE'

export interface IntakeReadiness {
  deal_stage: string
  offering_type: string
  offering_usage: string
  usage_depth: string
  deal_amount: string
  deal_close_date: string
  deal_notes: string
  signals_confirmed: boolean
}

export interface DealSnapshot {
  stage: string
  close_date: string | null
  amount: number | null
  notes: string | null
}

export interface ActivePatterns {
  primary: string | null
  secondary: string[]
}

export interface SessionState {
  session_id: string
  user_id: string
  opportunity_id: string
  state: SessionStateName
  intent_text: string | null
  deal_snapshot: DealSnapshot | null
  active_signals: string[]
  active_patterns: ActivePatterns
  selected_strategy_path: string | null
  lever_states: Record<string, string>
  interaction_history: Record<string, unknown>[]
  intake_readiness: IntakeReadiness
  intake_fields: Record<string, unknown>
  selected_action_key: string | null
  updated_at: string | null
}

export interface SessionSummary {
  session_id: string
  user_id: string
  opportunity_id: string
  state: SessionStateName
  updated_at: string | null
}

export interface PatternItem {
  key: string
  name: string
  summary: string
  diagnostic_questions: string[]
  resolution_type: 'RECOVER' | 'ADVANCE' | 'EXIT'
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  polarity: string
}

export interface PatternGroup {
  patterns: PatternItem[]
  meta_explanation: string
  needs_confirmation: boolean
  options: {
    confirm_all: string
    reject_all: string
    confirm_subset: string
  }
}

export interface ConfirmPatternsRequest {
  response: 'confirm_all' | 'reject_all' | 'confirm_subset'
  confirmed_keys?: string[]
}

export interface ConfirmPatternsResponse {
  state: SessionStateName
  confirmed_patterns: string[]
  strategy_path: string | null
  representative_actions: ActionItem[]
}

export interface ActionItem {
  action_key: string
  description: string
  ux_text: string
}

export interface SwaClientPrincipal {
  identityProvider: string
  userId: string
  userDetails: string
  userRoles: string[]
}

// ─── API request/response shapes ─────────────────────────────────────────────

export interface CreateSessionRequest {
  user_id: string
  opportunity_id: string
}

export interface InputRequest {
  input_type: 'button' | 'text' | 'attachment' | 'fields'
  signals?: string[]
  content?: string
  fields?: Record<string, string>
}

export interface ConfirmRequest {
  response: 'confirm' | 'adjust' | 'reject' | 'correct'
  deal_stage?: string
}

export interface SelectActionRequest {
  action_key: string
}

export interface DualPatternRequest {
  choice: 'focus' | 'combine' | 'sequence'
}

export interface ProposalItem {
  label: string
  value: string
}

export interface ConfirmationProposal {
  signals: ProposalItem[]
  deal_attributes: ProposalItem[]
  summary: string
}

export interface InputResponse {
  state: SessionStateName
  // Backend returns { items: [...], needs_confirmation: bool, options: [...] }
  // normalizeProposal() in App.tsx converts this to ConfirmationProposal
  proposal?: Record<string, unknown>
  message?: string
  // New fields from INTENT_CAPTURE → SITUATION_VALIDATION
  situation_summary?: string
  options?: string[]
  // New fields from INTAKE structured input
  next_prompt?: { field: string; prompt: string } | null
  signals_needed?: boolean
}

export interface DiagnosisResponse {
  state: SessionStateName
  primary_pattern?: string | null
  secondary_patterns?: string[]
  strategy_path?: string | null
  representative_actions?: ActionItem[]
  lever_states?: Record<string, string>
  // PATTERN_DIAGNOSTICS response
  pattern_group?: PatternGroup
}

export interface GeneralAssistResponse {
  response: string
}
