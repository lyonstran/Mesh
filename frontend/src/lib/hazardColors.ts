import type { RegionAlert } from './types'

// Same level colors as the HazardBanner: 1 yellow, 2 orange, 3 red (PLAN.md §7).
export const ALERT_COLORS: Record<number, { stroke: string; fill: string }> = {
  1: { stroke: '#ca8a04', fill: '#facc15' },
  2: { stroke: '#ea580c', fill: '#f97316' },
  3: { stroke: '#dc2626', fill: '#ef4444' },
}

/** Stable id for an alert in the region feed (NWS ids are URLs; fall back to its position). */
export function alertKey(alert: RegionAlert, index: number): string {
  return alert.properties.id ?? `alert-${index}`
}
