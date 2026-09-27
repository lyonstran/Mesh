import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useLogout, useMe, useSwitchMode } from '../api/hooks'
import { homeFor } from '../auth/home'
import type { Role } from '../lib/types'
import SimSwitch from './SimSwitch'

const MODES: { role: Role; label: string }[] = [
  { role: 'requester', label: 'Requester' },
  { role: 'helper', label: 'Volunteer' },
]

const navLink =
  'inline-flex min-h-10 items-center rounded-lg px-2.5 font-semibold whitespace-nowrap text-ink-soft transition-colors duration-150 hover:bg-ink/5 hover:text-ink sm:px-3'

/** App chrome for signed-in pages. The header is h-16 + 1px border; VolunteerHome sizes its map from that. */
export default function Layout() {
  const me = useMe()
  const logout = useLogout()
  const switchMode = useSwitchMode()
  const navigate = useNavigate()
  const user = me.data?.user
  // The volunteer page is a list beside a map that fill the whole page; everything else stays a narrow column.
  const fullPage = useLocation().pathname === '/h'
  const initial = user?.name?.trim()[0]?.toUpperCase() ?? '?'

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-ground/90 backdrop-blur">
        <div className="flex h-16 items-center justify-between gap-3 px-4 lg:px-6">
          <Link to={user ? homeFor(user.role) : '/'} className="flex items-center gap-2 text-xl font-extrabold tracking-tight">
            <img src="/logo.png" alt="" className="h-9 w-9 object-contain mix-blend-multiply" />
            <span className="max-sm:sr-only">Mesh</span>
          </Link>
          {user && (
            <div className="flex items-center gap-1 text-sm sm:gap-2">
              {user.role && <SimSwitch />}
              {user.role && user.roles.length > 1 ? (
                <div role="group" aria-label="Switch mode" className="mr-1 flex rounded-full bg-surface p-1 text-xs font-bold ring-1 ring-line">
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
                      className={`min-h-8 cursor-pointer rounded-full px-3 transition-colors duration-200 ${user.role === role ? 'bg-ink text-white' : 'text-ink-soft hover:text-ink'}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : (
                user.role && (
                  <span className="mr-1 rounded-full bg-brand-soft px-3 py-1 text-xs font-bold text-brand-strong ring-1 ring-brand/30">
                    {user.role === 'helper' ? 'Volunteer' : 'Requester'}
                  </span>
                )
              )}
              {user.role && (
                <Link to="/profile" className={navLink} title={user.name ?? undefined}>
                  <span className="mr-2 flex size-7 items-center justify-center rounded-full bg-ink text-xs font-bold text-white" aria-hidden>
                    {initial}
                  </span>
                  <span className="max-sm:sr-only">Profile</span>
                </Link>
              )}
              <button type="button" onClick={() => logout.mutate()} className={`${navLink} cursor-pointer`}>
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className={fullPage ? 'w-full' : 'mx-auto max-w-xl px-4 pt-8 pb-16'}>
        <Outlet />
      </main>
      {/* The volunteer page is a full-screen map; its tiles carry the OpenStreetMap credit instead. */}
      {!fullPage && (
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-xl flex-col gap-1 px-4 py-6 text-sm text-ink-soft sm:flex-row sm:justify-between">
            <p>Mesh is not an emergency service. If anyone's life is in danger, call 911.</p>
            <Link to="/about" className="font-semibold whitespace-nowrap underline underline-offset-4 hover:text-ink">
              Data sources and credits
            </Link>
          </div>
        </footer>
      )}
    </div>
  )
}
