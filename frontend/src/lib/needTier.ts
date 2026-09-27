// Need (the priority factor, 0-1) in four tiers. On the map it sets the pin's size (bigger = more need), so color
// stays free for state: navy by default, brand green when hovered or selected, red for a possible emergency.

export type NeedTier = 'lower' | 'moderate' | 'high' | 'critical'

export const NEED_TIERS: { tier: NeedTier; min: number; label: string; pinHeight: number }[] = [
  { tier: 'critical', min: 0.65, label: 'Critical need', pinHeight: 48 },
  { tier: 'high', min: 0.45, label: 'High need', pinHeight: 42 },
  { tier: 'moderate', min: 0.25, label: 'Moderate need', pinHeight: 37 },
  { tier: 'lower', min: 0, label: 'Lower need', pinHeight: 32 },
]

export function needTier(value: number) {
  return NEED_TIERS.find((t) => value >= t.min) ?? NEED_TIERS[NEED_TIERS.length - 1]
}

/** The `need` factor from a ranked request's breakdown (0.5 if it's somehow missing). */
export function needValue(breakdown: { key: string; value: number }[]): number {
  return breakdown.find((f) => f.key === 'need')?.value ?? 0.5
}

/** Pin colors, from the site palette (src/index.css). */
export const PIN_COLORS = {
  default: { fill: '#1e2a47', text: '#ffffff' }, // ink
  active: { fill: '#10b981', text: '#1e2a47' }, // brand, text on it is ink
  emergency: { fill: '#b42318', text: '#ffffff' }, // alert, reserved for the 911 path
}
