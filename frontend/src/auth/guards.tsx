import type { ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
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
      <div role="alert" className="mx-auto max-w-md px-4 py-16">
        <h1 className="text-2xl font-extrabold">Mesh can't reach its server</h1>
        <p className="mt-2 text-ink-soft">Check your connection and reload the page. If you're running Mesh locally, start the backend.</p>
        <Link to="/" className="mt-6 inline-block font-semibold underline underline-offset-4">
          Back to the home page
        </Link>
      </div>
    )
  }
  if (me.data.needs_onboarding && location.pathname !== '/onboarding') return <Navigate to="/onboarding" replace />
  return children
}

/** Sends users who don't hold this profile to their home page. The active mode doesn't matter here. */
export function RoleGuard({ role, children }: { role: Role; children: ReactNode }) {
  const me = useMe()
  const user = me.data?.user
  if (!user?.roles.includes(role)) return <Navigate to={homeFor(user?.role ?? null)} replace />
  return children
}
