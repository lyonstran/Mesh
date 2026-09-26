import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useMe } from '../api/hooks'
import { Loading } from '../components/ui'
import type { Role } from '../lib/types'
import { homeFor } from './home'

/** Signed-in users only: 401 → /login, no role yet → /onboarding. */
export function AuthGuard({ children }: { children: ReactNode }) {
  const me = useMe()
  const location = useLocation()

  if (me.isPending) return <Loading />
  if (me.error) {
    if (me.error instanceof ApiError && me.error.status === 401) return <Navigate to="/login" replace />
    return (
      <p role="alert" className="p-6 text-alert">
        Mesh can't reach its server right now. Check your connection and reload the page.
      </p>
    )
  }
  if (me.data.needs_onboarding && location.pathname !== '/onboarding') return <Navigate to="/onboarding" replace />
  return children
}

/** Sends users with a different role to their own home page. */
export function RoleGuard({ role, children }: { role: Role; children: ReactNode }) {
  const me = useMe()
  const userRole = me.data?.user.role ?? null
  if (userRole !== role) return <Navigate to={homeFor(userRole)} replace />
  return children
}

export function HomeRedirect() {
  const me = useMe()
  if (me.isPending) return <Loading />
  if (me.error) return <Navigate to="/login" replace />
  return <Navigate to={homeFor(me.data.user.role)} replace />
}
