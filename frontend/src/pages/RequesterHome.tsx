import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCheckEmergency, useCreateRequest, useMyRequests, useRequestAction } from '../api/hooks'
import EmergencyInterstitial from '../components/EmergencyInterstitial'
import { Button, ErrorText, Loading, inputClass } from '../components/ui'
import { STATUS_LABELS, timeAgo } from '../lib/labels'
import { stagger } from '../lib/motion'
import type { HelpRequest } from '../lib/types'

function NewRequestForm() {
  const [text, setText] = useState('')
  const [showEmergency, setShowEmergency] = useState(false)
  const check = useCheckEmergency()
  const create = useCreateRequest()

  const send = () => create.mutate(text.trim(), { onSuccess: () => setShowEmergency(false) })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    check.mutate(text.trim(), { onSuccess: ({ emergency }) => (emergency ? setShowEmergency(true) : send()) })
  }

  return (
    <form onSubmit={submit}>
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
      <Button type="submit" variant="accent" className="mt-4 w-full text-lg" disabled={text.trim().length < 3 || check.isPending || create.isPending}>
        {check.isPending || create.isPending ? 'Sending…' : 'Ask for help'}
      </Button>
      <ErrorText error={check.error ?? create.error} />
      {showEmergency && (
        <EmergencyInterstitial busy={create.isPending} onContinue={send} onBack={() => setShowEmergency(false)} />
      )}
    </form>
  )
}

function ActiveRequest({ request }: { request: HelpRequest }) {
  const action = useRequestAction()
  const claimed = request.status === 'CLAIMED'

  return (
    <section>
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
