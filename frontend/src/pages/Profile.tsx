import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMe, useUpdateProfile } from '../api/hooks'
import { homeFor } from '../auth/home'
import { BasicsFields, HelperProfileFields, RequesterFlagsFields } from '../components/ProfileFields'
import { Button, ErrorText, Loading } from '../components/ui'
import { EMPTY_FLAGS, EMPTY_HELPER, helperHasContent, type Basics } from '../lib/profile'
import type { HelperProfile, RequesterFlags, User } from '../lib/types'

function ProfileForm({ user }: { user: User }) {
  const update = useUpdateProfile()
  const role = user.role ?? 'requester'
  const isHelper = role === 'helper'

  const [basics, setBasics] = useState<Basics>({ name: user.name ?? '', language: user.language, background: user.background })
  const [helper, setHelper] = useState<HelperProfile>({ ...EMPTY_HELPER, ...user.helper })
  const [flags, setFlags] = useState<RequesterFlags>({ ...EMPTY_FLAGS, ...user.requester_flags })
  const [saved, setSaved] = useState(false)

  const edit =
    <T,>(setter: (v: T) => void) =>
    (v: T) => {
      setter(v)
      setSaved(false)
    }

  const canSave = basics.name.trim() && (!isHelper || helperHasContent(helper))

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    update.mutate(
      {
        name: basics.name.trim(),
        language: basics.language,
        background: basics.background.trim(),
        ...(isHelper ? { helper: { ...helper, about: helper.about.trim() } } : { requester_flags: flags }),
      },
      { onSuccess: () => setSaved(true) },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-8">
      <div>
        <Link to={homeFor(role)} className="text-sm font-semibold underline underline-offset-4">
          Back
        </Link>
        <h1 className="mt-2 text-3xl font-extrabold">Your profile</h1>
        <p className="mt-2 text-ink-soft">
          {isHelper
            ? 'Keep your skills and offer up to date. Requests are ranked for you based on what you write here.'
            : 'Details that help the volunteer who picks your request.'}
        </p>
      </div>

      <BasicsFields role={role} value={basics} onChange={edit(setBasics)} />
      {isHelper ? (
        <HelperProfileFields value={helper} onChange={edit(setHelper)} />
      ) : (
        <RequesterFlagsFields value={flags} onChange={edit(setFlags)} />
      )}

      <div className="sticky bottom-0 -mx-4 border-t border-line bg-ground/95 px-4 py-3 backdrop-blur">
        <Button type="submit" className="w-full" disabled={!canSave || update.isPending}>
          {update.isPending ? 'Saving…' : 'Save changes'}
        </Button>
        <p role="status" className="mt-2 min-h-5 text-sm text-ink-soft">
          {saved && (isHelper ? 'Saved. Your request rankings now reflect these changes.' : 'Saved.')}
          {!saved && isHelper && !helperHasContent(helper) && 'Pick at least one skill or item, or describe what you can offer.'}
        </p>
        <ErrorText error={update.error} />
      </div>
    </form>
  )
}

export default function Profile() {
  const me = useMe()
  if (me.isPending) return <Loading />
  if (!me.data) return <ErrorText error={me.error} />
  return <ProfileForm user={me.data.user} />
}
