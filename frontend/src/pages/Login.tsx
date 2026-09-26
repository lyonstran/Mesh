import { GoogleLogin } from '@react-oauth/google'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useDemoUsers, useLogin, useMe } from '../api/hooks'
import { homeFor } from '../auth/home'
import { Button, ErrorText, inputClass } from '../components/ui'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
const DEMO_LOGIN = import.meta.env.VITE_DEMO_LOGIN === 'true'

export default function Login() {
  const me = useMe()
  const login = useLogin()
  const navigate = useNavigate()
  const demoUsers = useDemoUsers(DEMO_LOGIN)
  const [demoId, setDemoId] = useState('')

  if (me.data) return <Navigate to={homeFor(me.data.user.role)} replace />

  const onLoggedIn = (data: { needs_onboarding: boolean; user: { role: 'requester' | 'helper' | null } }) =>
    navigate(data.needs_onboarding ? '/onboarding' : homeFor(data.user.role), { replace: true })

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col px-4 py-10">
      <p className="text-2xl font-extrabold tracking-tight">Mesh</p>

      <section className="mt-14">
        <h1 className="text-[2.35rem] leading-[1.1] font-extrabold">Help from the neighbors around you, after the storm.</h1>
        <p className="mt-4 max-w-prose text-lg text-ink-soft">
          Ask for help with what you need, or offer what you can do. Mesh matches requests with volunteers whose
          skills fit, then opens a private chat between you.
        </p>
      </section>

      <section className="mt-10 rounded-xl bg-surface p-5 shadow-[0_1px_0_var(--color-line)]">
        <h2 className="font-semibold">Sign in to continue</h2>
        <div className="mt-4 min-h-11">
          {GOOGLE_CLIENT_ID ? (
            <GoogleLogin
              onSuccess={({ credential }) => {
                if (credential) login.mutate({ kind: 'google', credential }, { onSuccess: onLoggedIn })
              }}
              onError={() => login.reset()}
              text="continue_with"
              shape="rectangular"
              width="320"
            />
          ) : (
            <p className="text-ink-soft">Google sign-in isn't set up yet. Add VITE_GOOGLE_CLIENT_ID to .env.</p>
          )}
        </div>

        {DEMO_LOGIN && (
          <form
            className="mt-6 border-t border-line pt-5"
            onSubmit={(e) => {
              e.preventDefault()
              if (demoId) login.mutate({ kind: 'demo', userId: demoId }, { onSuccess: onLoggedIn })
            }}
          >
            <label htmlFor="demo-user" className="font-semibold">
              Or try a demo account
            </label>
            <div className="mt-2 flex gap-2">
              <select id="demo-user" value={demoId} onChange={(e) => setDemoId(e.target.value)} className={inputClass}>
                <option value="">Choose a demo user</option>
                {demoUsers.data?.users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.role === 'helper' ? 'volunteer' : 'requester'})
                  </option>
                ))}
              </select>
              <Button type="submit" className="shrink-0" disabled={!demoId || login.isPending}>
                Sign in
              </Button>
            </div>
            {demoUsers.data?.users.length === 0 && (
              <p className="mt-2 text-sm text-ink-soft">No demo users yet. Run python -m app.seed --reset.</p>
            )}
          </form>
        )}
        <ErrorText error={login.error} />
      </section>

      <p className="mt-auto pt-10 text-sm text-ink-soft">
        Mesh is not an emergency service. If anyone's life is in danger, call 911.
      </p>
    </main>
  )
}
