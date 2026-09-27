// Mirrors backend/app/models.py and the response shapes in backend/app/services/serialize.py.
// Keep in sync.

export type LLMProviderName = 'mock' | 'muse'
export type VectorSearchMode = 'atlas' | 'local'

export interface Health {
  ok: boolean
  db: 'ok' | 'error'
  llm_provider: LLMProviderName
  vector_search: VectorSearchMode
  sim_active: boolean
}

export type Role = 'requester' | 'helper'
export type RequestStatus = 'OPEN' | 'CLAIMED' | 'RESOLVED' | 'CANCELLED'

export const SKILLS = [
  'first_aid',
  'cpr',
  'nursing',
  'chainsaw',
  'heavy_lifting',
  'driving',
  'spanish',
  'other_language',
  'electrical_safe',
  'childcare',
  'elder_care',
] as const
export type Skill = (typeof SKILLS)[number]

export const RESOURCES = [
  'vehicle',
  'truck',
  'generator',
  'power_bank',
  'water',
  'food',
  'tarp',
  'sandbags',
  'ac_space',
  'n95_masks',
  'medical_kit',
] as const
export type Resource = (typeof RESOURCES)[number]

// Limits mirror MAX_CUSTOM_SKILLS / MAX_CUSTOM_SKILL_LENGTH in backend/app/models.py.
export const MAX_CUSTOM_SKILLS = 10
export const MAX_CUSTOM_SKILL_LENGTH = 40

// Mirror MAX_RADIUS_KM / DEFAULT_RADIUS_KM in backend/app/models.py.
export const MAX_RADIUS_KM = 15
export const DEFAULT_RADIUS_KM = 10

/** API shape for a point: {lat, lon}. (Mongo stores GeoJSON [lon, lat]; only the backend touches that.) */
export interface LatLon {
  lat: number
  lon: number
}

export interface GeocodeMatch extends LatLon {
  label: string
}

export interface HelperProfile {
  skills: Skill[]
  custom_skills: string[] // volunteer-entered skills not in SKILLS
  resources: Resource[]
  about: string
  radius_km: number // how far from home_location the volunteer will travel
  show_area_to_requesters: boolean // appear as an approximate area on nearby requesters' maps
}

/** The other person's latest shared point on a claimed request. */
export interface LiveLocation extends LatLon {
  updated_at: string
  age_s: number // seconds since they last sent it
}

/** A volunteer as a requester sees them: an approximate area, nothing else. */
export interface NearbyVolunteer {
  display_location: LatLon
}

export interface RequesterFlags {
  medical_device: boolean
  mobility: boolean
  lives_alone: boolean
}

export interface User {
  id: string
  email: string | null
  name: string | null
  picture: string | null
  role: Role | null // active mode: decides the home page
  roles: Role[] // profiles the account holds; endpoint guards check this, not `role`
  home_location: LatLon | null
  language: string
  background: string
  helper: HelperProfile | null
  requester_flags: RequesterFlags | null
}

export interface MeResponse {
  user: User
  needs_onboarding: boolean
  rematching?: boolean // PATCH /api/me: true while the volunteer's matches are being refreshed in the background
}

export interface OnboardingBody {
  role: Role
  name: string
  language: string
  background: string
  home_location?: LatLon
  helper?: HelperProfile
  requester_flags?: RequesterFlags
}

/** POST /api/me/roles: add the profile the account doesn't have yet. */
export interface AddRoleBody {
  role: Role
  helper?: HelperProfile
  requester_flags?: RequesterFlags
}

export interface ProfileUpdate {
  role?: Role // switch the active mode (must be a held profile)
  name?: string
  language?: string
  background?: string
  home_location?: LatLon | null // null clears it
  helper?: HelperProfile
  requester_flags?: RequesterFlags
}

export interface Person {
  id: string
  name: string | null
}

export interface RequesterDetails extends Person {
  language: string
  background: string
  requester_flags: RequesterFlags | null
}

export interface TimelineEntry {
  status: RequestStatus
  at: string
  by: string | null
}

export interface HelpRequest {
  id: string
  text: string
  language: string
  status: RequestStatus
  emergency: boolean
  created_at: string
  updated_at: string
  viewer_relation: 'requester' | 'assigned_helper' | 'other'
  // Triage (null on requests saved before triage existed). Everyone sees these.
  category: Category | null
  urgency: number | null // 1-5
  summary: string | null
  needs: string[]
  score?: number
  display_location?: LatLon // fuzzed (300-500 m); everyone sees this
  // Only for the requester and the assigned volunteer:
  location?: LatLon // exact
  flags?: TriageFlag[] // vulnerability flags
  claimed_at?: string | null
  resolved_at?: string | null
  timeline?: TimelineEntry[]
  helper?: Person | null // requester's view
  requester?: RequesterDetails | null // assigned volunteer's view
}

export const CATEGORIES = [
  'power',
  'water',
  'food',
  'medical_supplies',
  'transport',
  'shelter',
  'cooling',
  'warming',
  'debris',
  'respiratory',
  'welfare_check',
  'supplies',
  'other',
] as const
export type Category = (typeof CATEGORIES)[number]

export type TriageFlag = 'medical_device' | 'mobility' | 'elderly' | 'lives_alone' | 'infant' | 'language_barrier'

/** POST /api/requests/preview: rules merged with AI. Urgency is never below urgency_rule_floor. */
export interface Triage {
  category: Category
  urgency: number // 1-5
  urgency_rule_floor: number // 1-5
  emergency: boolean
  flags: TriageFlag[]
  needs: string[]
  summary: string
  language: string
  source: 'ai' | 'rules' // 'rules' when the AI was off or failed
}

export interface RequestCreateBody {
  text: string
  location?: LatLon
  category_override?: Category // the requester's pick on the preview card; never changes urgency
}

export interface RankedResponse {
  requests: HelpRequest[]
  vector_search: VectorSearchMode
  profile_embedded: boolean
}

export interface Message {
  id: string
  request_id: string
  from_user_id: string
  mine: boolean
  text: string
  ts: string
}

export interface DemoUser {
  id: string
  name: string | null
  role: Role | null
}

export type HazardType = 'tornado' | 'severe_storm' | 'flood' | 'heat' | 'air_quality' | 'winter' | 'tropical' | 'wind' | 'other'
export type HazardSource = 'NWS' | 'Open-Meteo'
export type HazardSourceName = 'NWS' | 'Open-Meteo forecast' | 'Open-Meteo air quality'

/** One hazard (PLAN.md §7). NWS alerts are official; Open-Meteo signals are derived and capped at level 2. */
export interface Hazard {
  type: HazardType
  level: 1 | 2 | 3
  source: HazardSource
  official: boolean
  event: string | null // NWS event name
  headline: string | null
  expires: string | null // ISO
  instruction: string | null
  value: number | null // derived: the reading that crossed the threshold
  unit: string | null
  category: string | null // e.g. EPA AQI category
}

/** GET /api/hazards?lat&lon. Levels come from code, never the AI. */
export interface HazardReport {
  level: 0 | 1 | 2 | 3
  hazards: Hazard[]
  likely_needs: string[]
  current: {
    temperature_f?: number | null
    apparent_temperature_f?: number | null
    wind_gust_mph?: number | null
    precip_next_12h_in?: number | null
    us_aqi?: number | null
    pm2_5?: number | null
  }
  simulated: boolean
  sources_failed: HazardSourceName[]
  fetched_at: string // ISO
}
