import { Link, Outlet } from 'react-router-dom'
import { useLogout, useMe } from '../api/hooks'
import { homeFor } from '../auth/home'

/** App chrome for signed-in pages. */
export default function Layout() {
  const me = useMe()
  const logout = useLogout()
  const user = me.data?.user

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 bg-ink text-white">
        <div className="mx-auto flex max-w-xl items-center justify-between gap-3 px-4 py-3">
          <Link
            to={user ? homeFor(user.role) : '/'}
            className="flex items-center gap-2 text-xl font-extrabold tracking-tight"
          >
            <img src="/logo.png" alt="" className="h-9 w-9 rounded-md bg-white object-contain p-0.5" />
            Mesh
          </Link>
          {user && (
            <div className="flex items-center gap-3 text-sm">
              <span className="hidden max-w-32 truncate text-white/80 sm:inline">{user.name}</span>
              {user.role && (
                <span className="rounded bg-porch px-1.5 py-0.5 text-xs font-semibold text-ink">
                  {user.role === 'helper' ? 'Volunteer' : 'Requester'}
                </span>
              )}
              {user.role && (
                <Link to="/profile" className="flex min-h-10 items-center rounded-md px-2 font-semibold underline-offset-4 hover:underline">
                  Profile
                </Link>
              )}
              <button
                type="button"
                onClick={() => logout.mutate()}
                className="min-h-10 rounded-md px-2 font-semibold text-white underline-offset-4 hover:underline"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-xl px-4 pt-6 pb-16">
        <Outlet />
      </main>
    </div>
  )
}
