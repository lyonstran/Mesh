import { useState } from 'react'
import { stopSharingLocation, useOtherLocation } from '../api/hooks'
import { LiveMap } from './map/lazy'
import { Button } from './ui'
import { formatDistance, haversineKm } from '../lib/geo'
import { useLocationShare } from '../lib/useLocationShare'
import type { HelpRequest } from '../lib/types'

/** Whether this person agreed to share on this request. A per-device convenience, so it lives in the browser. */
function readShared(key: string): boolean {
  try {
    return localStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function writeShared(key: string, on: boolean) {
  try {
    if (on) localStorage.setItem(key, '1')
    else localStorage.removeItem(key)
  } catch {
    // Private mode or blocked storage: sharing still works for this visit.
  }
}

function seenText(name: string, ageS: number): string {
  if (ageS < 15) return `${name} is sharing their live location.`
  if (ageS < 90) return `${name} was last seen ${Math.round(ageS)} seconds ago.`
  return `${name} was last seen ${Math.round(ageS / 60)} minutes ago.`
}

/**
 * Live map for a claimed request: the request's exact spot, your own dot, and the other person's dot, both
 * updating while each of you is sharing. Sharing is opt-in on each side and stops when the request ends.
 */
export default function LiveTracking({ request, otherName }: { request: HelpRequest; otherName: string }) {
  const isVolunteer = request.viewer_relation === 'assigned_helper'
  const storageKey = `mesh:share:${request.id}`
  const [sharing, setSharing] = useState(() => readShared(storageKey))
  const { position: me, error } = useLocationShare(request.id, sharing)
  const other = useOtherLocation(request.id, true)
  const otherPoint = other.data?.other ?? null
  const simulated = other.data?.simulated === true
  const stale = otherPoint !== null && otherPoint.age_s > (other.data?.stale_after_s ?? 45)

  const pin = request.location ?? null
  const volunteerPoint = isVolunteer ? me : otherPoint
  const distanceKm = pin && volunteerPoint ? haversineKm(volunteerPoint, pin) : null

  const start = () => {
    writeShared(storageKey, true)
    setSharing(true)
  }
  const pause = () => {
    writeShared(storageKey, false)
    setSharing(false)
    stopSharingLocation(request.id).catch(() => {}) // the other person stops seeing you right away
  }

  return (
    <section aria-label="Live location" className="rounded-xl bg-surface p-4">
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-extrabold">Live location</h2>
        {simulated && (
          <span className="rounded bg-ink px-2 py-0.5 text-xs font-bold tracking-wide text-white">SIMULATED</span>
        )}
      </div>

      {sharing ? (
        <div className="mt-2 flex items-start justify-between gap-3">
          <p className="text-sm text-ink-soft">
            Sharing your location with {otherName} until this request ends. Only they can see it.
          </p>
          <Button type="button" variant="quiet" className="min-h-10 shrink-0 px-4" onClick={pause}>
            Pause
          </Button>
        </div>
      ) : (
        <div className="mt-2">
          <p className="text-sm text-ink-soft">
            Share your live location with {otherName} so you can find each other. Only {otherName} can see it, and it stops
            when you pause or when this request is resolved, cancelled, or handed back.
          </p>
          <Button type="button" className="mt-3 w-full" onClick={start}>
            Share my location with {otherName}
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-alert">
          {error}
        </p>
      )}

      <div className="mt-4">
        <LiveMap
          pin={pin}
          pinLabel={isVolunteer ? 'Request location' : 'Your request'}
          me={me}
          other={otherPoint}
          otherLabel={simulated ? `${otherName} (simulated)` : otherName}
          otherIsVolunteer={!isVolunteer}
          stale={stale}
        />
      </div>

      <p role="status" className="mt-3 text-sm text-ink-soft">
        {otherPoint ? seenText(otherName, otherPoint.age_s) : `${otherName} isn't sharing their location yet.`}
        {simulated && ' This is a demo account, so the location is simulated, not from a real device.'}
        {distanceKm !== null && (
          <>
            {' '}
            <span className="font-semibold text-ink">
              {isVolunteer ? 'You are' : `${otherName} is`} about {formatDistance(distanceKm)} from the request.
            </span>
          </>
        )}
      </p>

      {isVolunteer && pin && (
        <a
          href={`https://www.google.com/maps/dir/?api=1&destination=${pin.lat},${pin.lon}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex min-h-11 items-center font-semibold underline underline-offset-4"
        >
          Open directions in Google Maps
        </a>
      )}
    </section>
  )
}
