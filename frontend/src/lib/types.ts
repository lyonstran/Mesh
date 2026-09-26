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

export interface HelperProfile {
  skills: Skill[]
  resources: Resource[]
  about: string
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
  role: Role | null
  language: string
  background: string
  helper: HelperProfile | null
  requester_flags: RequesterFlags | null
}

export interface MeResponse {
  user: User
  needs_onboarding: boolean
}

export interface OnboardingBody {
  role: Role
  name: string
  language: string
  background: string
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
  score?: number
  // Only for the requester and the assigned volunteer:
  claimed_at?: string | null
  resolved_at?: string | null
  timeline?: TimelineEntry[]
  helper?: Person | null // requester's view
  requester?: RequesterDetails | null // assigned volunteer's view
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
