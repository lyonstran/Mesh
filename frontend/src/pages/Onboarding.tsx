import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useMe, useOnboarding } from '../api/hooks'
import { homeFor } from '../auth/home'
import { Button, ErrorText, Field, inputClass } from '../components/ui'
import { LANGUAGES, RESOURCE_LABELS, SKILL_LABELS } from '../lib/labels'
import { RESOURCES, SKILLS, type RequesterFlags, type Resource, type Role, type Skill } from '../lib/types'

const ROLE_CHOICES: { role: Role; title: string; body: string }[] = [
  { role: 'requester', title: 'I need help', body: 'Describe what you need and a volunteer who fits will reach out in a private chat.' },
  { role: 'helper', title: 'I can help', body: "Tell us what you can do and we'll show you the requests you're best suited for." },
]

const FLAG_LABELS: Record<keyof RequesterFlags, string> = {
  medical_device: 'I rely on a medical device that needs power',
  mobility: 'I have limited mobility',
  lives_alone: 'I live alone',
}

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item]
}

function Chip({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`min-h-11 rounded-full border px-4 text-sm font-semibold transition ${
        selected ? 'border-ink bg-ink text-white' : 'border-line bg-surface text-ink hover:border-ink-soft'
      }`}
    >
      {children}
    </button>
  )
}

export default function Onboarding() {
  const me = useMe()
  const onboarding = useOnboarding()
  const navigate = useNavigate()

  const [role, setRole] = useState<Role | null>(null)
  const [name, setName] = useState(me.data?.user.name ?? '')
  const [language, setLanguage] = useState('en')
  const [background, setBackground] = useState('')
  const [skills, setSkills] = useState<Skill[]>([])
  const [resources, setResources] = useState<Resource[]>([])
  const [about, setAbout] = useState('')
  const [flags, setFlags] = useState<RequesterFlags>({ medical_device: false, mobility: false, lives_alone: false })

  if (me.data && !me.data.needs_onboarding) return <Navigate to={homeFor(me.data.user.role)} replace />

  const canSubmit = role && name.trim() && (role === 'requester' || skills.length || resources.length || about.trim())

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!role) return
    onboarding.mutate(
      {
        role,
        name: name.trim(),
        language,
        background: background.trim(),
        ...(role === 'helper' ? { helper: { skills, resources, about: about.trim() } } : { requester_flags: flags }),
      },
      { onSuccess: (data) => navigate(homeFor(data.user.role), { replace: true }) },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-8">
      <div>
        <h1 className="text-3xl font-extrabold">Welcome to Mesh</h1>
        <p className="mt-2 text-ink-soft">A few details so we can connect you with the right people.</p>
      </div>

      <fieldset>
        <legend className="font-semibold">How do you want to use Mesh?</legend>
        <div className="mt-3 grid gap-3">
          {ROLE_CHOICES.map((c) => (
            <button
              key={c.role}
              type="button"
              aria-pressed={role === c.role}
              onClick={() => setRole(c.role)}
              className={`rounded-xl border-2 p-4 text-left transition ${
                role === c.role ? 'border-ink bg-porch-soft' : 'border-transparent bg-surface hover:border-line'
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
          <div className="space-y-5">
            <Field label="Your name">
              <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required />
            </Field>
            <Field label="Language you're most comfortable in">
              <select className={inputClass} value={language} onChange={(e) => setLanguage(e.target.value)}>
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="About you"
              hint={role === 'helper' ? 'Your work or experience, in a sentence or two.' : 'Anything a volunteer should know about you or your household.'}
            >
              <textarea className={`${inputClass} min-h-24`} value={background} onChange={(e) => setBackground(e.target.value)} maxLength={1000} />
            </Field>
          </div>

          {role === 'helper' ? (
            <div className="space-y-6">
              <fieldset>
                <legend className="font-semibold">Skills</legend>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SKILLS.map((s) => (
                    <Chip key={s} selected={skills.includes(s)} onClick={() => setSkills(toggle(skills, s))}>
                      {SKILL_LABELS[s]}
                    </Chip>
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend className="font-semibold">Things you can bring</legend>
                <div className="mt-3 flex flex-wrap gap-2">
                  {RESOURCES.map((r) => (
                    <Chip key={r} selected={resources.includes(r)} onClick={() => setResources(toggle(resources, r))}>
                      {RESOURCE_LABELS[r]}
                    </Chip>
                  ))}
                </div>
              </fieldset>
              <Field
                label="What can you offer?"
                hint="In your own words. This is what we match against requests, so be specific: “I can cut up fallen trees and haul debris in my truck.”"
              >
                <textarea className={`${inputClass} min-h-28`} value={about} onChange={(e) => setAbout(e.target.value)} maxLength={1000} />
              </Field>
            </div>
          ) : (
            <fieldset>
              <legend className="font-semibold">Anything that affects the help you need?</legend>
              <p className="mt-1 text-sm text-ink-soft">
                Optional. Only the volunteer who picks your request will see this.
              </p>
              <div className="mt-3 space-y-2">
                {(Object.keys(FLAG_LABELS) as (keyof RequesterFlags)[]).map((key) => (
                  <label key={key} className="flex min-h-11 items-center gap-3 rounded-lg bg-surface px-3">
                    <input
                      type="checkbox"
                      className="size-5 accent-ink"
                      checked={flags[key]}
                      onChange={(e) => setFlags({ ...flags, [key]: e.target.checked })}
                    />
                    {FLAG_LABELS[key]}
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          <div>
            <Button type="submit" className="w-full" disabled={!canSubmit || onboarding.isPending}>
              {onboarding.isPending ? 'Saving…' : 'Finish setup'}
            </Button>
            {role === 'helper' && !canSubmit && name.trim() && (
              <p className="mt-2 text-sm text-ink-soft">Pick at least one skill or item, or describe what you can offer.</p>
            )}
            <ErrorText error={onboarding.error} />
          </div>
        </>
      )}
    </form>
  )
}
