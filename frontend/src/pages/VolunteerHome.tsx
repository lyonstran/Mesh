import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useMyRequests, useRanked, useRequestAction } from '../api/hooks'
import { Button, ErrorText, Loading } from '../components/ui'
import { stagger } from '../lib/motion'
import { timeAgo } from '../lib/labels'
import type { HelpRequest } from '../lib/types'

/** Match strength as a filled green bar. Scores are (1 + cosine) / 2 from the backend; stretch the useful range. */
function MatchBar({ score }: { score?: number }) {
  if (score === undefined) return <div className="w-2 shrink-0 rounded-full bg-line" aria-hidden />
  const strength = Math.min(1, Math.max(0.08, (score - 0.5) * 2.5))
  return (
    <div className="relative w-2 shrink-0 overflow-hidden rounded-full bg-brand-soft" aria-hidden>
      <div className="animate-grow absolute inset-x-0 bottom-0 origin-bottom rounded-full bg-brand" style={{ height: `${strength * 100}%` }} />
    </div>
  )
}

function RankedItem({ request, rank, onClaim, busy }: { request: HelpRequest; rank: number; onClaim: () => void; busy: boolean }) {
  return (
    <li className="animate-rise stagger flex gap-4 rounded-xl bg-surface p-4" style={stagger(rank - 1)}>
      <MatchBar score={request.score} />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-ink-soft">
          {rank === 1 && request.score !== undefined ? 'Best fit for your profile, ' : ''}posted {timeAgo(request.created_at)}
          {request.language !== 'en' && ` (${request.language})`}
        </p>
        <p className="mt-1 text-lg">{request.text}</p>
        {request.emergency && (
          <p className="mt-2 text-sm font-semibold text-alert">May be an emergency. The requester was shown the option to call 911.</p>
        )}
        <Button variant={rank === 1 ? 'accent' : 'quiet'} className="mt-3" onClick={onClaim} disabled={busy}>
          Help with this
        </Button>
      </div>
    </li>
  )
}

export default function VolunteerHome() {
  const ranked = useRanked()
  const mine = useMyRequests(10_000)
  const action = useRequestAction()
  const navigate = useNavigate()
  const [claimingId, setClaimingId] = useState<string | null>(null)

  const claim = (id: string) => {
    setClaimingId(id)
    action.mutate(
      { id, action: 'claim' },
      { onSuccess: () => navigate(`/chat/${id}`), onSettled: () => setClaimingId(null) },
    )
  }

  const active = mine.data?.requests.filter((r) => r.status === 'CLAIMED') ?? []
  const alreadyTaken = action.error instanceof ApiError && action.error.code === 'ALREADY_CLAIMED'

  return (
    <div className="space-y-10">
      {active.length > 0 && (
        <section>
          <h2 className="text-xl font-extrabold">People you're helping</h2>
          <ul className="mt-3 space-y-3">
            {active.map((r, i) => (
              <li key={r.id} className="animate-rise stagger" style={stagger(i)}>
                <Link to={`/chat/${r.id}`} className="block rounded-xl border-l-4 border-brand bg-surface p-4 transition duration-200 hover:-translate-y-0.5 hover:bg-brand-soft hover:shadow-md">
                  <span className="block font-semibold">{r.requester?.name ?? 'Requester'}</span>
                  <span className="mt-1 line-clamp-2 block text-ink-soft">{r.text}</span>
                  <span className="mt-2 block font-semibold underline underline-offset-4">Open chat</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h1 className="text-3xl font-extrabold">Requests that fit you</h1>
        <p className="mt-2 text-ink-soft">
          Ranked by how closely each request matches the skills and offer in your profile. The list refreshes on its own.{' '}
          <Link to="/profile" className="font-semibold text-ink underline underline-offset-4">
            Edit your skills
          </Link>
        </p>

        {alreadyTaken && <p role="status" className="mt-4 rounded-lg bg-brand-soft p-3">Another volunteer just picked that one. Here's the updated list.</p>}
        {!alreadyTaken && <ErrorText error={action.error} />}

        {ranked.isPending && <Loading label="Finding requests" />}
        {ranked.error && <ErrorText error={ranked.error} />}
        {ranked.data && !ranked.data.profile_embedded && (
          <p className="mt-4 rounded-lg bg-brand-soft p-3">
            <Link to="/profile" className="font-semibold underline underline-offset-4">
              Add skills or describe what you can offer
            </Link>{' '}
            so we can rank requests for you. Until then, newest requests come first.
          </p>
        )}
        {ranked.data?.requests.length === 0 && (
          <p className="mt-6 rounded-xl bg-surface p-5 text-ink-soft">
            No open requests right now. New ones will show up here automatically.
          </p>
        )}
        <ol className="mt-5 space-y-3">
          {ranked.data?.requests.map((r, i) => (
            <RankedItem key={r.id} request={r} rank={i + 1} onClaim={() => claim(r.id)} busy={claimingId !== null} />
          ))}
        </ol>
      </section>
    </div>
  )
}
