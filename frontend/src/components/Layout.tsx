import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useLogout, useMe, useSwitchMode } from '../api/hooks'
import { homeFor } from '../auth/home'
import type { Role } from '../lib/types'

const MODES: { role: Role; label: string }[] = [
  { role: 'requester', label: 'Requester' },
  { role: 'helper', label: 'Volunteer' },
]

/** App chrome for signed-in pages. */
export default function Layout() {
  const me = useMe()
  const logout = useLogout()
  const switchMode = useSwitchMode()
  const navigate = useNavigate()
  const user = me.data?.user
  // The volunteer page is a list beside a map that fill the whole page; everything else stays a narrow column.
  const fullPage = useLocation().pathname === '/h'

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-ground/95 backdrop-blur">
        <div className="mx-auto flex min-h-16 max-w-5xl items-center justify-between gap-4 px-4 py-2">
          <Link
            to={user ? homeFor(user.role) : '/'}
            className="flex items-center gap-2 text-xl font-extrabold tracking-tight"
          >
            <img src="/logo.png" alt="" className="h-10 w-10 object-contain mix-blend-multiply" />
            Mesh
          </Link>
          {user && (
            <div className="flex items-center gap-3 text-sm sm:gap-10">
              <span className="hidden max-w-32 truncate text-ink-soft sm:inline">{user.name}</span>
              {user.role && user.roles.length > 1 ? (
                <div role="group" aria-label="Switch mode" className="flex rounded-md bg-ink/5 p-0.5 text-xs font-semibold">
                  {MODES.map(({ role, label }) => (
                    <button
                      key={role}
                      type="button"
                      aria-pressed={user.role === role}
                      disabled={switchMode.isPending}
                      onClick={() => {
                        if (user.role === role) return
                        switchMode.mutate(role, { onSuccess: () => navigate(homeFor(role)) })
                      }}
                      className={`min-h-9 cursor-pointer rounded px-2 transition-colors duration-200 ${user.role === role ? 'bg-brand text-ink' : 'text-ink-soft hover:text-ink'}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : (
                user.role && (
                  <span className="rounded bg-brand px-1.5 py-0.5 text-xs font-semibold text-ink">
                    {user.role === 'helper' ? 'Volunteer' : 'Requester'}
                  </span>
                )
              )}
              {user.role && (
                <Link to="/profile" className="flex min-h-10 items-center rounded-md px-2 font-semibold whitespace-nowrap text-ink-soft underline-offset-4 hover:text-ink hover:underline">
                  Profile
                </Link>
              )}
              <button
                type="button"
                onClick={() => logout.mutate()}
                className="min-h-10 rounded-md px-2 font-semibold whitespace-nowrap text-ink-soft underline-offset-4 hover:text-ink hover:underline"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className={fullPage ? 'w-full' : 'mx-auto max-w-xl px-4 pt-6 pb-16'}>
        <Outlet />
      </main>
      {/* The volunteer page is a full-screen map; its tiles carry the OpenStreetMap credit instead. */}
      {!fullPage && (
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-xl flex-col gap-1 px-4 py-6 text-sm text-ink-soft">
            <p>Mesh is not an emergency service. If anyone's life is in danger, call 911.</p>
            <Link to="/about" className="font-semibold underline underline-offset-4 hover:text-ink">
              Data sources and credits
            </Link>
          </div>
        </footer>
      )}
    </div>
  )
}
