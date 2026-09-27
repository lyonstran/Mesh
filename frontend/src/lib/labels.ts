import type { Category, HazardType, RequestStatus, Resource, Skill, TriageFlag } from './types'

export const SKILL_LABELS: Record<Skill, string> = {
  first_aid: 'First aid',
  cpr: 'CPR',
  nursing: 'Nursing',
  chainsaw: 'Chainsaw',
  heavy_lifting: 'Heavy lifting',
  driving: 'Driving',
  spanish: 'Spanish',
  other_language: 'Another language',
  electrical_safe: 'Electrical safety',
  childcare: 'Childcare',
  elder_care: 'Elder care',
}

export const RESOURCE_LABELS: Record<Resource, string> = {
  vehicle: 'Car or van',
  truck: 'Truck',
  generator: 'Generator',
  power_bank: 'Power banks',
  water: 'Drinking water',
  food: 'Food',
  tarp: 'Tarps',
  sandbags: 'Sandbags',
  ac_space: 'Cool space (A/C)',
  n95_masks: 'N95 masks',
  medical_kit: 'Medical kit',
}

export const LANGUAGES: { code: string; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Español' },
  { code: 'other', label: 'Other' },
]

export const CATEGORY_LABELS: Record<Category, string> = {
  power: 'Power',
  water: 'Drinking water',
  food: 'Food',
  medical_supplies: 'Medicine or medical supplies',
  transport: 'A ride',
  shelter: 'Shelter',
  cooling: 'Cooling off',
  warming: 'Staying warm',
  debris: 'Trees or debris',
  respiratory: 'Smoke or breathing',
  welfare_check: 'Checking on someone',
  supplies: 'Supplies',
  other: 'Something else',
}

export const URGENCY_LABELS: Record<number, string> = {
  1: 'Can wait a few days',
  2: 'Needed within a day',
  3: 'Needed within hours',
  4: 'Health or safety at risk',
  5: 'Life in danger',
}

export const FLAG_LABELS: Record<TriageFlag, string> = {
  medical_device: 'Relies on a medical device',
  mobility: 'Limited mobility',
  elderly: 'Older adult',
  lives_alone: 'Lives alone',
  infant: 'Infant',
  language_barrier: 'Language help needed',
}

export const HAZARD_LABELS: Record<HazardType, string> = {
  tornado: 'Tornado',
  severe_storm: 'Severe storm',
  flood: 'Flooding',
  heat: 'Heat',
  air_quality: 'Air quality',
  winter: 'Winter weather',
  tropical: 'Tropical storm',
  wind: 'High wind',
  other: 'Weather alert',
}

export const HAZARD_LEVEL_LABELS: Record<number, string> = {
  0: 'No active hazards',
  1: 'Minor hazard',
  2: 'Elevated hazard',
  3: 'Severe hazard',
}

export const STATUS_LABELS: Record<RequestStatus, string> = {
  OPEN: 'Waiting for a volunteer',
  CLAIMED: 'A volunteer is helping',
  RESOLVED: 'Resolved',
  CANCELLED: 'Cancelled',
}

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

export function timeAgo(iso: string): string {
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000)
  const abs = Math.abs(seconds)
  if (abs < 60) return rtf.format(seconds, 'second')
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(seconds / 3600), 'hour')
  return rtf.format(Math.round(seconds / 86400), 'day')
}
