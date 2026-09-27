import type { HelpRequest, TimelineEntry } from '../lib/types'

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })
const fullFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

/** One line per status change, written from the requester's side. */
function describe(entry: TimelineEntry, index: number, request: HelpRequest, viewerId: string | undefined): string {
  const helper = request.helper
  const byCurrentHelper = helper !== null && helper !== undefined && entry.by === helper.id
  switch (entry.status) {
    case 'OPEN':
      return index === 0 ? 'You posted your request' : 'The volunteer handed it back, so it is open again'
    case 'CLAIMED':
      return byCurrentHelper && helper?.name ? `${helper.name} picked it up` : 'A volunteer picked it up'
    case 'RESOLVED':
      if (entry.by === viewerId) return 'You marked it resolved'
      return byCurrentHelper && helper?.name ? `${helper.name} marked it resolved` : 'Marked resolved'
    case 'CANCELLED':
      return 'You cancelled it'
  }
}

/** What has happened to a request so far, oldest first. The serializer sends `timeline` only to the two participants. */
export default function StatusTimeline({ request, viewerId }: { request: HelpRequest; viewerId?: string }) {
  const entries = request.timeline ?? []
  if (entries.length === 0) return null
  return (
    <section aria-label="What's happened so far" className="mt-6">
      <h2 className="font-semibold">What's happened so far</h2>
      <ol className="mt-3">
        {entries.map((entry, i) => {
          const latest = i === entries.length - 1
          const at = new Date(entry.at)
          return (
            <li key={`${entry.status}-${entry.at}`} className="relative flex gap-3 pb-4 last:pb-0">
              {!latest && <span aria-hidden className="absolute top-4 bottom-0 left-[5px] w-0.5 bg-line" />}
              <span
                aria-hidden
                className={`relative mt-1.5 h-3 w-3 shrink-0 rounded-full ${latest ? 'bg-brand ring-4 ring-brand-soft' : 'bg-ink-soft/50'}`}
              />
              <p className={latest ? 'font-semibold' : 'text-ink-soft'}>
                {describe(entry, i, request, viewerId)}
                <time dateTime={entry.at} title={fullFormat.format(at)} className="ml-2 text-sm font-normal text-ink-soft">
                  {timeFormat.format(at)}
                </time>
              </p>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
