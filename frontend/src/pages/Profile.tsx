import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAddRole, useMe, useUpdateProfile } from '../api/hooks'
import { homeFor } from '../auth/home'
import { BasicsFields, HelperProfileFields, RequesterFlagsFields } from '../components/ProfileFields'
import { ApiError } from '../api/client'
import { Button, ErrorText, Loading } from '../components/ui'
import { EMPTY_FLAGS, EMPTY_HELPER, helperHasContent, type Basics } from '../lib/profile'
import { useToast } from '../lib/toast'
import type { HelperProfile, ProfileUpdate, RequesterFlags, Role, User } from '../lib/types'

function saveError(err: unknown, what: string): string {
  return err instanceof ApiError
    ? `Couldn't ${what}: ${err.message}`
    : `Couldn't ${what}. Mesh can't reach its server; check your connection and try again.`
}

const TABS: { role: Role; label: string }[] = [
  { role: 'requester', label: 'Requester' },
  { role: 'helper', label: 'Volunteer' },
]

/** Requester | Volunteer tabs. Arrow keys move between them, as in the WAI-ARIA tabs pattern. */
function ProfileTabs({ active, held, onChange }: { active: Role; held: Role[]; onChange: (r: Role) => void }) {
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
    const next = TABS[(TABS.findIndex((t) => t.role === active) + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length]
    onChange(next.role)
    document.getElementById(`profile-tab-${next.role}`)?.focus()
  }
  return (
    <div role="tablist" aria-label="Profile" className="flex border-b border-line" onKeyDown={onKeyDown}>
      {TABS.map(({ role, label }) => (
        <button
          key={role}
          id={`profile-tab-${role}`}
          type="button"
          role="tab"
          aria-selected={active === role}
          aria-controls="profile-panel"
          tabIndex={active === role ? 0 : -1}
          onClick={() => onChange(role)}
          className={`-mb-px min-h-11 flex-1 cursor-pointer border-b-2 px-4 font-semibold transition-colors duration-200 sm:flex-none sm:px-8 ${
            active === role ? 'border-emerald-600 text-ink' : 'border-transparent text-ink-soft hover:text-ink'
          }`}
        >
          {label}
          {!held.includes(role) && <span className="ml-1 text-sm font-normal">(add)</span>}
        </button>
      ))}
    </div>
  )
}

function ProfileForm({ user, tab, onTabChange }: { user: User; tab: Role; onTabChange: (r: Role) => void }) {
  const update = useUpdateProfile()
  const toast = useToast()
  const held = user.roles
  const tabHeld = held.includes(tab)

  // State lives here so edits survive switching tabs; each tab saves its own profile plus the shared basics.
  const [basics, setBasics] = useState<Basics>({ name: user.name ?? '', language: user.language, background: user.background })
  const [helper, setHelper] = useState<HelperProfile>({ ...EMPTY_HELPER, ...user.helper })
  const [flags, setFlags] = useState<RequesterFlags>({ ...EMPTY_FLAGS, ...user.requester_flags })

  const isHelperTab = tab === 'helper'
  const canSave = !isHelperTab || helperHasContent(helper)
  const canSaveGeneral = basics.name.trim().length > 0

  const save = (fields: ProfileUpdate) =>
    update.mutate(fields, {
      onSuccess: (data) =>
        toast({
          kind: 'success',
          message: data.rematching ? 'Saved. Your matches will update in a few seconds.' : 'Saved.',
        }),
      onError: (err) => toast({ kind: 'error', message: saveError(err, 'save your changes') }),
    })

  const submitGeneral = (e: React.FormEvent) => {
    e.preventDefault()
    save({ name: basics.name.trim(), language: basics.language, background: basics.background.trim() })
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save(isHelperTab ? { helper: { ...helper, about: helper.about.trim() } } : { requester_flags: flags })
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to={homeFor(user.role ?? 'requester')} className="text-sm font-semibold underline underline-offset-4">
          Back
        </Link>
        <h1 className="mt-2 text-3xl font-extrabold">Your profile</h1>
        <p className="mt-2 text-ink-soft">
          {held.length > 1
            ? 'One account, two profiles. Switch modes from the bar at the top.'
            : 'Keep your details up to date. You can add the other profile to this account too.'}
        </p>
      </div>

      <form onSubmit={submitGeneral} className="space-y-5 rounded-xl bg-surface p-5">
        <h2 className="text-xl font-extrabold">General info</h2>
        <p className="-mt-3 text-sm text-ink-soft">Shared by your requester and volunteer profiles.</p>
        <BasicsFields value={basics} onChange={setBasics} />
        <Button type="submit" variant="quiet" disabled={!canSaveGeneral || update.isPending}>
          {update.isPending ? 'Saving…' : 'Save general info'}
        </Button>
      </form>

      <ProfileTabs active={tab} held={held} onChange={onTabChange} />

      <div role="tabpanel" id="profile-panel" aria-labelledby={`profile-tab-${tab}`}>
        {tabHeld ? (
          <form onSubmit={submit} className="space-y-8">
            <p className="text-ink-soft">
              {isHelperTab
                ? 'Keep your skills and offer up to date. Requests are ranked for you based on what you write here.'
                : 'Details that help the volunteer who picks your request.'}
            </p>
            {isHelperTab ? (
              <HelperProfileFields value={helper} onChange={setHelper} />
            ) : (
              <RequesterFlagsFields value={flags} onChange={setFlags} />
            )}

            <div className="sticky bottom-0 -mx-4 border-t border-line bg-ground/95 px-4 py-3 backdrop-blur">
              <Button type="submit" className="w-full" disabled={!canSave || update.isPending}>
                {update.isPending ? 'Saving…' : 'Save changes'}
              </Button>
              {isHelperTab && !helperHasContent(helper) && (
                <p className="mt-2 text-sm text-ink-soft">Pick at least one skill or item, or describe what you can offer.</p>
              )}
            </div>
          </form>
        ) : (
          <AddProfileCard missing={tab} />
        )}
      </div>
    </div>
  )
}

/** Lets a single-profile user add the other profile to the same account. */
function AddProfileCard({ missing }: { missing: Role }) {
  const addRole = useAddRole()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [helper, setHelper] = useState<HelperProfile>(EMPTY_HELPER)
  const [flags, setFlags] = useState<RequesterFlags>(EMPTY_FLAGS)
  const wantsHelper = missing === 'helper'
  const title = wantsHelper ? 'Become a volunteer' : 'Request help'

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    addRole.mutate(
      wantsHelper ? { role: 'helper', helper: { ...helper, about: helper.about.trim() } } : { role: 'requester', requester_flags: flags },
      {
        onSuccess: () => {
          setOpen(false)
          toast({ kind: 'success', message: wantsHelper ? 'Volunteer profile added. Switch to it from the top bar.' : 'Requester profile added. Switch to it from the top bar.' })
        },
        onError: (err) => toast({ kind: 'error', message: saveError(err, 'add that profile') }),
      },
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xl font-extrabold">{title}</h2>
      <p className="mt-1 text-ink-soft">
        {wantsHelper
          ? 'Add a volunteer profile to your account to help neighbors, as well as ask for help yourself.'
          : 'Add a requester profile to your account so you can ask for help too.'}
      </p>
      {open ? (
        <form onSubmit={submit} className="mt-4 space-y-6">
          {wantsHelper ? <HelperProfileFields value={helper} onChange={setHelper} /> : <RequesterFlagsFields value={flags} onChange={setFlags} />}
          <div className="flex gap-3">
            <Button type="submit" disabled={addRole.isPending || (wantsHelper && !helperHasContent(helper))}>
              {addRole.isPending ? 'Adding…' : title}
            </Button>
            <Button type="button" variant="quiet" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
          {wantsHelper && !helperHasContent(helper) && (
            <p className="text-sm text-ink-soft">Pick at least one skill or item, or describe what you can offer.</p>
          )}
        </form>
      ) : (
        <Button type="button" className="mt-4" onClick={() => setOpen(true)}>
          {title}
        </Button>
      )}
    </section>
  )
}

export default function Profile() {
  const me = useMe()
  const [tab, setTab] = useState<Role | null>(null)
  if (me.isPending) return <Loading />
  if (!me.data) return <ErrorText error={me.error} />
  const user = me.data.user
  // Keyed by the profiles held, so the forms reload from the server after one is added.
  return <ProfileForm key={user.roles.join()} user={user} tab={tab ?? user.role ?? 'requester'} onTabChange={setTab} />
}
