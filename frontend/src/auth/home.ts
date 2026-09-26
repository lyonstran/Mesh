import type { Role } from '../lib/types'

export function homeFor(role: Role | null): string {
  if (role === 'requester') return '/r'
  if (role === 'helper') return '/h'
  return '/onboarding'
}
