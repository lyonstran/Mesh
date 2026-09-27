import { useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { useMe } from '../api/hooks'
import { homeFor } from '../auth/home'

const NAV_LINKS = [
  { href: '/#how-it-works', label: 'How it works' },
  { href: '/#volunteering', label: 'Volunteering' },
  { href: '/#safety', label: 'Safety' },
]

/** Chrome for public pages. Renders fully without the backend; signed-in state is a bonus. */
export default function PublicLayout() {
  const me = useMe()
  const [menuOpen, setMenuOpen] = useState(false)
  const signedInHome = me.data ? homeFor(me.data.user.role) : null

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-ground/95 backdrop-blur">
        <nav aria-label="Main" className="mx-auto flex h-16 max-w-5xl items-center gap-2 px-4">
          <Link
            to="/"
            className="mr-auto flex items-center gap-2 text-2xl font-extrabold tracking-tight"
            onClick={() => setMenuOpen(false)}
          >
            <img src="/logo.png" alt="" className="h-10 w-10 object-contain mix-blend-multiply" />
            Mesh
          </Link>

          <ul className="hidden items-center gap-1 sm:flex">
            {NAV_LINKS.map((l) => (
              <li key={l.href}>
                <a href={l.href} className="rounded-md px-3 py-2 font-semibold text-ink-soft hover:text-ink">
                  {l.label}
                </a>
              </li>
            ))}
          </ul>

          <button
            type="button"
            className="min-h-11 rounded-md px-3 font-semibold text-ink-soft hover:text-ink sm:hidden"
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            onClick={() => setMenuOpen((o) => !o)}
          >
            {menuOpen ? 'Close' : 'Menu'}
          </button>

          <Link
            to={signedInHome ?? '/login'}
            onClick={() => setMenuOpen(false)}
            className="inline-flex min-h-11 items-center rounded-lg bg-ink px-4 font-semibold text-white hover:bg-ink/90 sm:ml-2"
          >
            {signedInHome ? 'Open Mesh' : 'Log in'}
          </Link>
        </nav>

        {menuOpen && (
          <ul id="mobile-nav" className="mx-auto max-w-5xl border-t border-line px-4 pb-3 sm:hidden">
            {NAV_LINKS.map((l) => (
              <li key={l.href}>
                <a href={l.href} className="block py-3 font-semibold" onClick={() => setMenuOpen(false)}>
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        )}
      </header>

      <div className="flex-1">
        <Outlet />
      </div>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-5xl flex-col gap-2 px-4 py-8 text-sm text-ink-soft sm:flex-row sm:justify-between">
          <p>Mesh is not an emergency service. If anyone's life is in danger, call 911.</p>
          <p>
            Built at HackGT 13.{' '}
            <Link to="/about" className="font-semibold underline underline-offset-4 hover:text-ink">
              Data sources and credits
            </Link>
          </p>
        </div>
      </footer>
    </div>
  )
}
