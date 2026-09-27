import { useEffect, useRef, useState } from 'react'
import { postLocation } from '../api/hooks'
import { haversineKm } from './geo'
import type { LatLon } from './types'

const SEND_EVERY_MS = 10_000 // PLAN.md §10: at most every 10 s...
const MOVED_M = 25 // ...or sooner after moving this far

function geolocationMessage(err: GeolocationPositionError): string {
  return err.code === err.PERMISSION_DENIED
    ? 'Location permission is blocked. Allow it in your browser settings to share your location.'
    : "Can't get your location right now. Sharing will resume when your device finds a signal."
}

/**
 * While `sharing`, watches this device's position and sends it to the other person on the request.
 * Returns the local position (for drawing your own dot) and any error. Does nothing, and asks the browser for
 * nothing, while `sharing` is false.
 */
export function useLocationShare(requestId: string, sharing: boolean) {
  const [position, setPosition] = useState<LatLon | null>(null)
  const [error, setError] = useState<string | null>(null)
  const last = useRef<{ at: number; point: LatLon } | null>(null)
  const supported = typeof navigator !== 'undefined' && 'geolocation' in navigator

  useEffect(() => {
    if (!sharing || !supported) return
    last.current = null
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const point = { lat: pos.coords.latitude, lon: pos.coords.longitude }
        setPosition(point)
        setError(null)
        const previous = last.current
        const now = Date.now()
        if (previous && now - previous.at < SEND_EVERY_MS && haversineKm(previous.point, point) * 1000 < MOVED_M) return
        last.current = { at: now, point }
        // A dropped or failed update is fine: the next fix (or the next poll on the other side) catches up.
        postLocation(requestId, { ...point, accuracy: pos.coords.accuracy }).catch(() => {})
      },
      (err) => setError(geolocationMessage(err)),
      { enableHighAccuracy: true, maximumAge: 10_000, timeout: 20_000 },
    )
    return () => {
      navigator.geolocation.clearWatch(watchId)
      setPosition(null)
    }
  }, [requestId, sharing, supported])

  return {
    position: sharing ? position : null,
    error: sharing ? (supported ? error : "This browser can't share your location.") : null,
  }
}
