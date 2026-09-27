import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useMe, useMyRequests, useRanked, useRequestAction } from '../api/hooks'
import HazardBanner from '../components/HazardBanner'
import { RequestsMap } from '../components/map/lazy'
import { Button, ErrorText, Loading } from '../components/ui'
import { stagger } from '../lib/motion'
import { useMediaQuery } from '../lib/useMediaQuery'
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

function RankedItem({
  request,
  rank,
  selected,
  onSelect,
  onClaim,
  busy,
}: {
  request: HelpRequest
  rank: number
  selected: boolean
  onSelect: () => void
  onClaim: () => void
  busy: boolean
}) {
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [selected])
  return (
    <li
      ref={ref}
      onClick={onSelect}
      className={`animate-rise stagger flex cursor-pointer gap-4 rounded-xl bg-surface p-4 ${selected ? 'ring-2 ring-emerald-600' : ''}`}
      style={stagger(rank - 1)}
    >
      <MatchBar score={request.score} />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-ink-soft">
          {rank === 1 && request.score !== undefined ? 'Best fit for your profile, ' : ''}posted {timeAgo(request.created_at)}
          {request.language !== 'en' && ` (${request.language})`}
        </p>
        {!request.display_location && <p className="mt-1 text-sm text-ink-soft">No location shared, so it isn't on the map.</p>}
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
  const me = useMe()
  const home = me.data?.user.home_location ?? null
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = useState(true)
  const wide = useMediaQuery('(min-width: 1024px)')
  // Space the floating list covers, so the map fits and centers on what's left visible.
  const insets = wide ? { left: 480, bottom: 0 } : { left: 0, bottom: sheetOpen ? Math.round(window.innerHeight * 0.5) : 56 }
  const [claimingId, setClaimingId] = useState<string | null>(null)

  const claim = (id: string) => {
    setClaimingId(id)
    action.mutate(
      { id, action: 'claim' },
      { onSuccess: () => navigate(`/chat/${id}`), onSettled: () => setClaimingId(null) },
    )
  }

  const count = ranked.data?.requests.length ?? 0
  const unmapped = ranked.data?.requests.filter((r) => !r.display_location).length ?? 0
  const active = mine.data?.requests.filter((r) => r.status === 'CLAIMED') ?? []
  const alreadyTaken = action.error instanceof ApiError && action.error.code === 'ALREADY_CLAIMED'

  return (
    // The map is the page background and stays interactive. The list floats over it: a left panel from lg up,
    // a bottom sheet below that. Only the panel captures pointer events; the rest of the page is the map.
    <div className="relative h-[calc(100svh-4.0625rem)] overflow-hidden">
      <div className="absolute inset-0">
        <RequestsMap
          requests={ranked.data?.requests ?? []}
          home={home}
          selectedId={selectedId}
          onSelect={setSelectedId}
          className="h-full"
          note={false}
          background
          insets={insets}
        />
      </div>
      <aside
        aria-label="Requests"
        className={`animate-rise absolute inset-x-0 bottom-0 z-10 flex flex-col rounded-t-2xl bg-ground/90 shadow-[0_-8px_30px_-8px_rgba(30,42,71,0.35)] ring-1 ring-ink/10 backdrop-blur-md lg:inset-x-auto lg:top-4 lg:bottom-4 lg:left-4 lg:w-[26rem] lg:rounded-2xl lg:shadow-[0_12px_40px_-12px_rgba(30,42,71,0.45)] ${
          sheetOpen ? 'max-h-[55%]' : ''
        } lg:max-h-none`}
      >
        <button
          type="button"
          onClick={() => setSheetOpen((o) => !o)}
          aria-expanded={sheetOpen}
          className="flex min-h-12 w-full cursor-pointer items-center justify-between px-4 font-semibold lg:hidden"
        >
          <span>{count === 0 ? 'No open requests' : `${count} open ${count === 1 ? 'request' : 'requests'}`}</span>
          <span className="text-sm text-ink-soft">{sheetOpen ? 'Show map' : 'Show list'}</span>
        </button>
        <div className={`min-h-0 flex-1 space-y-10 overflow-y-auto px-4 pb-8 lg:block lg:pt-6 ${sheetOpen ? '' : 'hidden'}`}>
      <HazardBanner point={home} />
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

        {!home && (
          <p className="mt-4 rounded-lg bg-brand-soft p-3">
            <Link to="/profile" className="font-semibold underline underline-offset-4">
              Set your home location
            </Link>{' '}
            so the map centers on you and we can find requests near you.
          </p>
        )}

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
        {unmapped > 0 && (
          <p className="mt-4 text-sm text-ink-soft">
            {unmapped} of {count} {count === 1 ? 'request' : 'requests'} didn't include a location, so {unmapped === 1 ? 'it is' : 'they are'} listed but not on the map.
          </p>
        )}
        {ranked.data?.requests.length === 0 && (
          <p className="mt-6 rounded-xl bg-surface p-5 text-ink-soft">
            No open requests right now. New ones will show up here automatically.
          </p>
        )}
        <ol className="mt-5 space-y-3">
          {ranked.data?.requests.map((r, i) => (
            <RankedItem
              key={r.id}
              request={r}
              rank={i + 1}
              selected={r.id === selectedId}
              onSelect={() => setSelectedId(r.id)}
              onClaim={() => claim(r.id)}
              busy={claimingId !== null}
            />
          ))}
        </ol>
        <p className="mt-6 text-sm text-ink-soft">
          Circles on the map show an approximate area (about 500 m). Exact addresses are shared only with the volunteer who takes the request.
        </p>
      </section>
        </div>
      </aside>
    </div>
  )
}
