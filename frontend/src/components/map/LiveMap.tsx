import { useEffect } from 'react'
import { Marker, Polyline, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { LatLon, LiveLocation } from '../../lib/types'
import { dotIcon } from './icons'
import MapView from './MapView'

const PIN_ICON = dotIcon('#10b981', '#ffffff', 28) // where the help is needed
const ME_ICON = dotIcon('#1e2a47', '#ffffff', 22)
const OTHER_ICON = dotIcon('#047857', '#ffffff', 24)

function FitTo({ points, fitKey }: { points: LatLon[]; fitKey: string }) {
  const map = useMap()
  useEffect(() => {
    if (points.length === 0) return
    if (points.length === 1) {
      map.setView([points[0].lat, points[0].lon], 15, { animate: false })
      return
    }
    map.fitBounds(L.latLngBounds(points.map((p) => [p.lat, p.lon] as [number, number])), { padding: [64, 64], maxZoom: 16, animate: false })
    // Refit when a dot appears or disappears, not on every position update, so the user can pan and zoom freely.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, fitKey])
  return null
}

/**
 * The request's exact location, this person's own live dot, and the other person's live dot, with a dashed line
 * from the volunteer to the request. Only ever rendered for the requester and the assigned volunteer.
 */
export default function LiveMap({
  pin,
  pinLabel,
  me,
  other,
  otherLabel,
  otherIsVolunteer,
  stale,
}: {
  pin: LatLon | null
  pinLabel: string
  me: LatLon | null
  other: LiveLocation | null
  otherLabel: string
  otherIsVolunteer: boolean
  stale: boolean
}) {
  const points = [pin, me, other].filter((p): p is LatLon => p !== null)
  const volunteerPoint = otherIsVolunteer ? other : me
  return (
    <MapView center={pin ?? undefined} zoom={15} className="h-72 rounded-xl border border-line" label="Live map" wheelZoom>
      <FitTo points={points} fitKey={`${pin ? 'p' : ''}${me ? 'm' : ''}${other ? 'o' : ''}`} />
      {pin && volunteerPoint && (
        <Polyline
          positions={[[volunteerPoint.lat, volunteerPoint.lon], [pin.lat, pin.lon]]}
          pathOptions={{ color: '#047857', weight: 3, dashArray: '6 8', opacity: 0.8 }}
        />
      )}
      {pin && (
        <Marker position={[pin.lat, pin.lon]} icon={PIN_ICON}>
          <Tooltip permanent direction="top" offset={[0, -14]}>
            {pinLabel}
          </Tooltip>
        </Marker>
      )}
      {me && (
        <Marker position={[me.lat, me.lon]} icon={ME_ICON}>
          <Tooltip permanent direction="bottom" offset={[0, 12]}>
            You
          </Tooltip>
        </Marker>
      )}
      {other && (
        <Marker position={[other.lat, other.lon]} icon={OTHER_ICON} opacity={stale ? 0.45 : 1}>
          <Tooltip permanent direction="bottom" offset={[0, 12]}>
            {otherLabel}
          </Tooltip>
        </Marker>
      )}
    </MapView>
  )
}
