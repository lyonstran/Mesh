import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useMe, useOnboarding } from '../api/hooks'
import { homeFor } from '../auth/home'
import { BasicsFields, HelperProfileFields, RequesterFlagsFields } from '../components/ProfileFields'
import { Button, ErrorText } from '../components/ui'
import { EMPTY_FLAGS, EMPTY_HELPER, helperHasContent, type Basics } from '../lib/profile'
import { stagger } from '../lib/motion'
import type { HelperProfile, RequesterFlags, Role } from '../lib/types'

const ROLE_CHOICES: { role: Role; title: string; body: string }[] = [
  { role: 'requester', title: 'I need help', body: 'Describe what you need and a volunteer who fits will reach out in a private chat.' },
  { role: 'helper', title: 'I can help', body: "Tell us what you can do and we'll show you the requests you're best suited for." },
]

export default function Onboarding() {
  const me = useMe()
  const onboarding = useOnboarding()
  const navigate = useNavigate()

  const [role, setRole] = useState<Role | null>(null)
  const [basics, setBasics] = useState<Basics>({ name: me.data?.user.name ?? '', language: 'en', background: '' })
  const [helper, setHelper] = useState<HelperProfile>(EMPTY_HELPER)
  const [flags, setFlags] = useState<RequesterFlags>(EMPTY_FLAGS)

  if (me.data && !me.data.needs_onboarding) return <Navigate to={homeFor(me.data.user.role)} replace />

  const canSubmit = role && basics.name.trim() && (role === 'requester' || helperHasContent(helper))

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!role) return
    onboarding.mutate(
      {
        role,
        name: basics.name.trim(),
        language: basics.language,
        background: basics.background.trim(),
        ...(role === 'helper' ? { helper: { ...helper, about: helper.about.trim() } } : { requester_flags: flags }),
      },
      { onSuccess: (data) => navigate(homeFor(data.user.role), { replace: true }) },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-8">
      <div className="animate-rise">
        <h1 className="text-3xl font-extrabold">Welcome to Mesh</h1>
        <p className="mt-2 text-ink-soft">A few details so we can connect you with the right people.</p>
      </div>

      <fieldset>
        <legend className="font-semibold">How do you want to use Mesh?</legend>
        <div className="mt-3 grid gap-3">
          {ROLE_CHOICES.map((c, i) => (
            <button
              key={c.role}
              type="button"
              aria-pressed={role === c.role}
              onClick={() => setRole(c.role)}
              style={stagger(i + 1)}
              className={`animate-rise stagger cursor-pointer rounded-xl border-2 p-4 text-left transition duration-200 active:scale-[0.99] ${
                role === c.role ? 'border-emerald-600 bg-brand-soft' : 'border-transparent bg-surface hover:border-emerald-600/40'
              }`}
            >
              <span className="block text-lg font-extrabold">{c.title}</span>
              <span className="mt-1 block text-ink-soft">{c.body}</span>
            </button>
          ))}
        </div>
      </fieldset>

      {role && (
        <>
          <BasicsFields role={role} value={basics} onChange={setBasics} />
          {role === 'helper' ? (
            <HelperProfileFields value={helper} onChange={setHelper} />
          ) : (
            <RequesterFlagsFields value={flags} onChange={setFlags} />
          )}

          <div>
            <Button type="submit" className="w-full" disabled={!canSubmit || onboarding.isPending}>
              {onboarding.isPending ? 'Saving…' : 'Finish setup'}
            </Button>
            {role === 'helper' && !canSubmit && basics.name.trim() && (
              <p className="mt-2 text-sm text-ink-soft">Pick at least one skill or item, or describe what you can offer.</p>
            )}
            <p className="mt-2 text-sm text-ink-soft">You can change all of this later from your profile.</p>
            <ErrorText error={onboarding.error} />
          </div>
        </>
      )}
    </form>
  )
}
