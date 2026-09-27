import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAddRole, useMe, useUpdateProfile } from '../api/hooks'
import { homeFor } from '../auth/home'
import { BasicsFields, HelperProfileFields, RequesterFlagsFields } from '../components/ProfileFields'
import { ApiError } from '../api/client'
import { Button, ErrorText, Loading } from '../components/ui'
import { EMPTY_FLAGS, EMPTY_HELPER, helperHasContent, type Basics } from '../lib/profile'
import { useToast } from '../lib/toast'
import type { HelperProfile, RequesterFlags, Role, User } from '../lib/types'

function saveError(err: unknown, what: string): string {
  return err instanceof ApiError
    ? `Couldn't ${what}: ${err.message}`
    : `Couldn't ${what}. Mesh can't reach its server; check your connection and try again.`
}

function ProfileForm({ user }: { user: User }) {
  const update = useUpdateProfile()
  const toast = useToast()
  const role = user.role ?? 'requester'
  const isHelper = user.roles.includes('helper')
  const isRequester = user.roles.includes('requester')

  const [basics, setBasics] = useState<Basics>({ name: user.name ?? '', language: user.language, background: user.background })
  const [helper, setHelper] = useState<HelperProfile>({ ...EMPTY_HELPER, ...user.helper })
  const [flags, setFlags] = useState<RequesterFlags>({ ...EMPTY_FLAGS, ...user.requester_flags })

  const canSave = basics.name.trim() && (!isHelper || helperHasContent(helper))

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    update.mutate(
      {
        name: basics.name.trim(),
        language: basics.language,
        background: basics.background.trim(),
        ...(isHelper ? { helper: { ...helper, about: helper.about.trim() } } : {}),
        ...(isRequester ? { requester_flags: flags } : {}),
      },
      {
        onSuccess: (data) =>
          toast({
            kind: 'success',
            message: data.rematching ? 'Profile saved. Your matches will update in a few seconds.' : 'Profile saved.',
          }),
        onError: (err) => toast({ kind: 'error', message: saveError(err, 'save your profile') }),
      },
    )
  }

  const both = isHelper && isRequester

  return (
    <div className="space-y-8">
      <form onSubmit={submit} className="space-y-8">
        <div>
          <Link to={homeFor(role)} className="text-sm font-semibold underline underline-offset-4">
            Back
          </Link>
          <h1 className="mt-2 text-3xl font-extrabold">Your profile</h1>
          <p className="mt-2 text-ink-soft">
            {both
              ? 'One account, two profiles. Switch between them from the bar at the top.'
              : isHelper
                ? 'Keep your skills and offer up to date. Requests are ranked for you based on what you write here.'
                : 'Details that help the volunteer who picks your request.'}
          </p>
        </div>

        <BasicsFields role={role} value={basics} onChange={setBasics} />
        {isHelper && (
          <section className="space-y-4">
            {both && <h2 className="text-xl font-extrabold">Volunteer profile</h2>}
            <HelperProfileFields value={helper} onChange={setHelper} />
          </section>
        )}
        {isRequester && (
          <section className="space-y-4">
            {both && <h2 className="text-xl font-extrabold">Requester profile</h2>}
            <RequesterFlagsFields value={flags} onChange={setFlags} />
          </section>
        )}

        <div className="sticky bottom-0 -mx-4 border-t border-line bg-ground/95 px-4 py-3 backdrop-blur">
          <Button type="submit" className="w-full" disabled={!canSave || update.isPending}>
            {update.isPending ? 'Saving…' : 'Save changes'}
          </Button>
          {isHelper && !helperHasContent(helper) && (
            <p className="mt-2 text-sm text-ink-soft">Pick at least one skill or item, or describe what you can offer.</p>
          )}
        </div>
      </form>

      {!both && <AddProfileCard missing={isHelper ? 'requester' : 'helper'} />}
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
  if (me.isPending) return <Loading />
  if (!me.data) return <ErrorText error={me.error} />
  return <ProfileForm user={me.data.user} />
}
