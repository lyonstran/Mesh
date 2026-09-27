import { useEffect } from 'react'
import { Circle, Marker, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { LatLon, NearbyVolunteer } from '../../lib/types'
import { HOME_ICON } from './icons'
import MapView from './MapView'

/** Volunteers' points are fuzzed 300-500 m on the server, so each circle is an area, never a home. */
const AREA_RADIUS_M = 500

function FitTo({ points, fitKey }: { points: LatLon[]; fitKey: string }) {
  const map = useMap()
  useEffect(() => {
    if (points.length === 0) return
    map.fitBounds(L.latLngBounds(points.map((p) => [p.lat, p.lon] as [number, number])).pad(0.25), { maxZoom: 14 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, fitKey])
  return null
}

/** The requester's own pin plus the approximate areas of volunteers around them. */
export default function VolunteersMap({ center, volunteers }: { center: LatLon; volunteers: NearbyVolunteer[] }) {
  const points = [center, ...volunteers.map((v) => v.display_location)]
  return (
    <MapView center={center} zoom={13} label="Map of volunteers near you">
      <FitTo points={points} fitKey={`${center.lat},${center.lon},${volunteers.length}`} />
      <Marker position={[center.lat, center.lon]} icon={HOME_ICON}>
        <Tooltip>You</Tooltip>
      </Marker>
      {volunteers.map((v, i) => (
        <Circle
          key={i}
          center={[v.display_location.lat, v.display_location.lon]}
          radius={AREA_RADIUS_M}
          pathOptions={{ color: '#047857', fillColor: '#10b981', fillOpacity: 0.28, weight: 1.5 }}
        >
          <Tooltip>A volunteer nearby</Tooltip>
        </Circle>
      ))}
    </MapView>
  )
}
