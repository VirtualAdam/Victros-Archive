import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Lever, Pattern, RepresentativeAction, SalesZone, Signal, StrategyPath } from '../types'

const FOREVER = { staleTime: Infinity } as const

/** All 23 signals. */
export function useSignals() {
  return useQuery<Signal[]>({ queryKey: ['schema', 'signals'], queryFn: api.getSignals, ...FOREVER })
}

/** All 22 patterns. */
export function usePatterns() {
  return useQuery<Pattern[]>({ queryKey: ['schema', 'patterns'], queryFn: api.getPatterns, ...FOREVER })
}

/** All 13 strategy paths. */
export function useStrategyPaths() {
  return useQuery<StrategyPath[]>({ queryKey: ['schema', 'strategy-paths'], queryFn: api.getStrategyPaths, ...FOREVER })
}

/** All 7 levers. */
export function useLevers() {
  return useQuery<Lever[]>({ queryKey: ['schema', 'levers'], queryFn: api.getLevers, ...FOREVER })
}

/** All 4 sales zones. */
export function useSalesZones() {
  return useQuery<SalesZone[]>({ queryKey: ['schema', 'sales-zones'], queryFn: api.getSalesZones, ...FOREVER })
}

/** All 85 representative actions. */
export function useRepresentativeActions() {
  return useQuery<RepresentativeAction[]>({ queryKey: ['schema', 'representative-actions'], queryFn: api.getRepresentativeActions, ...FOREVER })
}

/** Look up a pattern by key. */
export function usePatternByKey(key: string | null) {
  const { data } = usePatterns()
  return data?.find((p) => p.key === key) ?? null
}

/** Look up a strategy path by key. */
export function useStrategyPathByKey(key: string | null) {
  const { data } = useStrategyPaths()
  return data?.find((sp) => sp.key === key) ?? null
}

/** Look up a lever by key. */
export function useLeverByKey(key: string | null) {
  const { data } = useLevers()
  return data?.find((l) => l.key === key) ?? null
}

/** All actions for a given strategy path key. */
export function useActionsByStrategyPath(strategyPathKey: string | null) {
  const { data = [] } = useRepresentativeActions()
  if (!strategyPathKey) return []
  return data.filter((a) => a.parent_strategy_path === strategyPathKey)
}
