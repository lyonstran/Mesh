import { GoogleLogin } from '@react-oauth/google'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useDemoUsers, useLogin, useMe } from '../api/hooks'
import { homeFor } from '../auth/home'
import { Button, inputClass } from '../components/ui'
import type { MeResponse } from '../lib/types'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
const DEMO_LOGIN = import.meta.env.VITE_DEMO_LOGIN === 'true'

const SERVER_DOWN = "Mesh can't reach its server right now. Check your connection and try again in a moment."

/** fetch() rejects with a TypeError when the server is unreachable; ApiErrors carry the server's message. */
function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return SERVER_DOWN
}

export default function Login() {
  const me = useMe()
  const login = useLogin()
  const navigate = useNavigate()
  const demoUsers = useDemoUsers(DEMO_LOGIN)
  const [demoId, setDemoId] = useState('')

  if (me.data) return <Navigate to={homeFor(me.data.user.role)} replace />

  const onLoggedIn = (data: MeResponse) => navigate(data.needs_onboarding ? '/onboarding' : homeFor(data.user.role), { replace: true })

  return (
    <main className="mx-auto max-w-md px-4 py-12">
      <h1 className="text-3xl font-extrabold">Log in to Mesh</h1>
      <p className="mt-2 text-ink-soft">New here? Logging in creates your account; you'll choose whether you need help or can help next.</p>

      <section className="mt-8 rounded-xl bg-surface p-5 shadow-[0_1px_0_var(--color-line)]">
        <div className="min-h-11">
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
              <select
                id="demo-user"
                value={demoId}
                onChange={(e) => setDemoId(e.target.value)}
                className={inputClass}
                disabled={!demoUsers.data}
              >
                <option value="">{demoUsers.isPending ? 'Loading demo users…' : 'Choose a demo user'}</option>
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
            {demoUsers.isError && <p className="mt-2 text-sm text-alert">{loginErrorMessage(demoUsers.error)}</p>}
            {demoUsers.data?.users.length === 0 && (
              <p className="mt-2 text-sm text-ink-soft">No demo users yet. Run python -m app.seed --reset.</p>
            )}
          </form>
        )}

        {login.error && (
          <p role="alert" className="mt-3 text-alert">
            {loginErrorMessage(login.error)}
          </p>
        )}
      </section>
    </main>
  )
}
