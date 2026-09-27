import type { HelperProfile, RequesterFlags } from './types'

export interface Basics {
  name: string
  language: string
  background: string
}

export const EMPTY_HELPER: HelperProfile = { skills: [], custom_skills: [], resources: [], about: '' }
export const EMPTY_FLAGS: RequesterFlags = { medical_device: false, mobility: false, lives_alone: false }

/** A volunteer needs at least one skill, item, or description so we have something to match on. */
export function helperHasContent(h: HelperProfile): boolean {
  return h.skills.length > 0 || h.custom_skills.length > 0 || h.resources.length > 0 || h.about.trim().length > 0
}
