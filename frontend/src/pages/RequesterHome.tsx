import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useCheckEmergency,
  useCreateRequest,
  useMe,
  useMyRequests,
  useNearbyVolunteers,
  usePreviewRequest,
  useRequestAction,
} from '../api/hooks'
import EmergencyInterstitial from '../components/EmergencyInterstitial'
import HazardBanner from '../components/HazardBanner'
import LiveTracking from '../components/LiveTracking'
import { LocationPicker, VolunteersMap } from '../components/map/lazy'
import { Button, ErrorText, Field, Loading, inputClass } from '../components/ui'
import { CATEGORY_LABELS, FLAG_LABELS, STATUS_LABELS, URGENCY_LABELS, timeAgo } from '../lib/labels'
import { stagger } from '../lib/motion'
import { CATEGORIES, type Category, type HelpRequest, type LatLon, type Triage } from '../lib/types'

/** Step 2 of submitting: how Mesh read the request. The category can be corrected; urgency is shown, not editable. */
function TriageCard({
  text,
  triage,
  category,
  onCategory,
  onSend,
  onEdit,
  busy,
  error,
}: {
  text: string
  triage: Triage
  category: Category
  onCategory: (c: Category) => void
  onSend: () => void
  onEdit: () => void
  busy: boolean
  error: unknown
}) {
  return (
    <section aria-labelledby="review-title">
      <h1 id="review-title" className="animate-rise text-3xl font-extrabold">Check your request</h1>
      <p className="mt-2 text-ink-soft">This is what volunteers will see first. Fix the type of help if we got it wrong.</p>

      <div className="animate-rise stagger mt-6 space-y-5 rounded-xl bg-surface p-5" style={stagger(1)}>
        <div>
          <p className="text-sm font-semibold text-ink-soft">Your words</p>
          <p className="mt-1 text-lg">{text}</p>
        </div>
        {triage.source === 'ai' && (
          <div>
            <p className="text-sm font-semibold text-ink-soft">Summary for volunteers</p>
            <p className="mt-1">{triage.summary}</p>
          </div>
        )}
        <Field label="Type of help">
          <select className={inputClass} value={category} onChange={(e) => onCategory(e.target.value as Category)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c]}
              </option>
            ))}
          </select>
        </Field>
        <div>
          <p className="font-semibold">How urgent</p>
          <p className="mt-1">
            <span className="font-extrabold">{triage.urgency} of 5</span>: {URGENCY_LABELS[triage.urgency]}
          </p>
          <p className="mt-1 text-sm text-ink-soft">Set from your words and your profile. If it's more urgent, go back and say so.</p>
        </div>
        {triage.flags.length > 0 && (
          <ul aria-label="Noted for your volunteer" className="flex flex-wrap gap-2">
            {triage.flags.map((f) => (
              <li key={f} className="rounded-full bg-brand-soft px-3 py-1 text-sm font-semibold">
                {FLAG_LABELS[f]}
              </li>
            ))}
          </ul>
        )}
        {triage.source === 'rules' && (
          <p className="text-sm text-ink-soft">The AI review wasn't available, so we sorted this by keywords. Check the type of help.</p>
        )}
      </div>

      <div className="mt-6 grid gap-3">
        <Button type="button" variant="accent" className="text-lg" onClick={onSend} disabled={busy}>
          {busy ? 'Sending…' : 'Send request'}
        </Button>
        <Button type="button" variant="quiet" onClick={onEdit} disabled={busy}>
          Go back and edit
        </Button>
      </div>
      <ErrorText error={error} />
    </section>
  )
}

function NewRequestForm() {
  const me = useMe()
  const [text, setText] = useState('')
  const [location, setLocation] = useState<LatLon | null>(me.data?.user.home_location ?? null)
  const [showEmergency, setShowEmergency] = useState(false)
  const [review, setReview] = useState<{ triage: Triage; category: Category } | null>(null)
  const check = useCheckEmergency()
  const preview = usePreviewRequest()
  const create = useCreateRequest()
  const draft = () => ({ text: text.trim(), ...(location ? { location } : {}) })

  const send = (category?: Category) =>
    create.mutate({ ...draft(), ...(category ? { category_override: category } : {}) }, { onSuccess: () => setShowEmergency(false) })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    // The keyword check is instant and never waits on the AI, so the 911 screen comes first (CLAUDE.md rule 6).
    check.mutate(text.trim(), {
      onSuccess: ({ emergency }) => {
        if (emergency) return setShowEmergency(true)
        preview.mutate(draft(), { onSuccess: ({ triage }) => setReview({ triage, category: triage.category }) })
      },
    })
  }

  if (review) {
    return (
      <TriageCard
        text={text.trim()}
        triage={review.triage}
        category={review.category}
        onCategory={(category) => setReview({ ...review, category })}
        // Send the category only when the requester changed it.
        onSend={() => send(review.category !== review.triage.category ? review.category : undefined)}
        onEdit={() => setReview(null)}
        busy={create.isPending}
        error={create.error}
      />
    )
  }

  const busy = check.isPending || preview.isPending || create.isPending
  return (
    <form onSubmit={submit}>
      <HazardBanner point={location} className="mb-6" />
      <h1 className="animate-rise text-3xl font-extrabold">What do you need help with?</h1>
      <p className="animate-rise stagger mt-2 text-ink-soft" style={stagger(1)}>
        Say what happened and what would help. The more specific you are, the better we can match you with a volunteer.
      </p>
      <label htmlFor="request-text" className="sr-only">
        Your request
      </label>
      <textarea
        id="request-text"
        className={`${inputClass} mt-5 min-h-36 text-lg`}
        placeholder="A tree fell across my driveway and I can't get my car out."
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={1000}
      />
      <section className="mt-6">
        <h2 className="text-xl font-extrabold">Where are you?</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Volunteers see only an approximate area (within about 500 m). Your exact spot goes only to the volunteer who takes your request.
        </p>
        <div className="mt-3">
          <LocationPicker value={location} onChange={setLocation} />
        </div>
      </section>
      <Button type="submit" variant="accent" className="mt-6 w-full text-lg" disabled={text.trim().length < 3 || !location || busy}>
        {preview.isPending ? 'Reading your request…' : busy ? 'Sending…' : 'Continue'}
      </Button>
      {preview.isPending && (
        <p role="status" className="mt-2 text-sm text-ink-soft">
          Our AI is sorting your request for volunteers. This takes a few seconds.
        </p>
      )}
      {!location && text.trim().length >= 3 && <p className="mt-2 text-sm text-ink-soft">Set your location so a nearby volunteer can find you.</p>}
      <ErrorText error={check.error ?? preview.error ?? create.error} />
      {showEmergency && (
        // In an emergency, send straight away: the review step would only add delay, and urgency is already 5.
        <EmergencyInterstitial busy={create.isPending} onContinue={() => send()} onBack={() => setShowEmergency(false)} />
      )}
    </form>
  )
}

/** Approximate areas of volunteers around the requester, shown while the request is waiting for someone to pick it up. */
function NearbyVolunteers({ center }: { center: LatLon | null }) {
  const nearby = useNearbyVolunteers(center)
  if (!center || nearby.isPending || nearby.error) return null
  const count = nearby.data.volunteers.length
  return (
    <section className="mt-6">
      <h2 className="text-xl font-extrabold">Volunteers near you</h2>
      <p className="mt-1 text-sm text-ink-soft">
        {count === 0
          ? 'No volunteers are showing an area near you right now. Your request is still visible to every volunteer, and new ones see it as soon as they open Mesh.'
          : `${count} ${count === 1 ? 'volunteer is' : 'volunteers are'} sharing an approximate area near you. Circles are about 500 m across, never an address.`}
      </p>
      <div className="mt-3">
        <VolunteersMap center={center} volunteers={nearby.data.volunteers} />
      </div>
    </section>
  )
}

function ActiveRequest({ request }: { request: HelpRequest }) {
  const action = useRequestAction()
  const claimed = request.status === 'CLAIMED'

  return (
    <section>
      <HazardBanner point={request.location ?? request.display_location} className="mb-6" />
      <h1 className="animate-rise text-3xl font-extrabold">{claimed ? `${request.helper?.name ?? 'A volunteer'} is helping you` : 'Your request is posted'}</h1>
      <p className="mt-2 text-ink-soft">
        {claimed
          ? 'Use the chat to agree on the details. You can mark it resolved when you have what you need.'
          : 'Volunteers whose skills fit your request can see it now. This page updates on its own.'}
      </p>

      <div className={`animate-rise stagger mt-6 rounded-xl bg-surface p-5 ${claimed ? 'border-l-4 border-brand' : ''}`} style={stagger(1)}>
        <p className="text-sm font-semibold text-ink-soft">
          {STATUS_LABELS[request.status]}, posted {timeAgo(request.created_at)}
        </p>
        <p className="mt-2 text-lg">{request.text}</p>
      </div>

      {claimed && <div className="mt-6"><LiveTracking request={request} otherName={request.helper?.name ?? 'your volunteer'} /></div>}
      {request.status === 'OPEN' && <NearbyVolunteers center={request.location ?? request.display_location ?? null} />}

      <div className="mt-5 grid gap-3">
        {claimed && (
          <Link
            to={`/chat/${request.id}`}
            className="inline-flex min-h-12 items-center justify-center rounded-lg bg-brand px-5 font-semibold text-ink transition duration-150 hover:bg-emerald-400 active:scale-[0.98]"
          >
            Open chat with {request.helper?.name ?? 'your volunteer'}
          </Link>
        )}
        {claimed && (
          <Button variant="quiet" disabled={action.isPending} onClick={() => action.mutate({ id: request.id, action: 'resolve' })}>
            I have what I need
          </Button>
        )}
        <Button
          variant="danger"
          disabled={action.isPending}
          onClick={() => {
            if (window.confirm('Cancel this request? Volunteers will no longer see it.')) action.mutate({ id: request.id, action: 'cancel' })
          }}
        >
          Cancel request
        </Button>
      </div>
      <ErrorText error={action.error} />
    </section>
  )
}

export default function RequesterHome() {
  const mine = useMyRequests()
  if (mine.isPending) return <Loading />
  if (mine.error) return <ErrorText error={mine.error} />

  const active = mine.data.requests.find((r) => r.status === 'OPEN' || r.status === 'CLAIMED')
  const past = mine.data.requests.filter((r) => r !== active)

  return (
    <div className="space-y-12">
      {active ? <ActiveRequest request={active} /> : <NewRequestForm />}

      {past.length > 0 && (
        <section>
          <h2 className="font-semibold">Earlier requests</h2>
          <ul className="mt-3 divide-y divide-line rounded-xl bg-surface">
            {past.map((r) => (
              <li key={r.id} className="p-4">
                <p className="line-clamp-2">{r.text}</p>
                <p className="mt-1 text-sm text-ink-soft">
                  {STATUS_LABELS[r.status]}, {timeAgo(r.updated_at)}
                  {r.status === 'RESOLVED' && (
                    <>
                      {' '}
                      <Link to={`/chat/${r.id}`} className="font-semibold text-ink underline underline-offset-4">
                        View chat
                      </Link>
                    </>
                  )}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
