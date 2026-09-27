import { useEffect } from 'react'
import { Circle, Marker, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { HelpRequest, LatLon } from '../../lib/types'
import { HOME_ICON } from './icons'
import MapView from './MapView'

/** The fuzzed point is 300-500 m from the real one, so the circle shows an area, never an address. */
const AREA_RADIUS_M = 500
const EDGE_PX = 32

/** Pixels of the map covered by an overlay. Fitting and centering leave that part clear. */
export interface Insets {
  left: number
  bottom: number
}

function FitTo({ points, fitKey, insets }: { points: LatLon[]; fitKey: string; insets: Insets }) {
  const map = useMap()
  useEffect(() => {
    if (points.length === 0) return
    map.fitBounds(L.latLngBounds(points.map((p) => [p.lat, p.lon] as [number, number])), {
      paddingTopLeft: [insets.left + EDGE_PX, EDGE_PX],
      paddingBottomRight: [EDGE_PX, insets.bottom + EDGE_PX],
      maxZoom: 15,
    })
    // Refit when the set of points or the overlay changes, not on every 10 s poll.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, fitKey, insets.left, insets.bottom])
  return null
}

function FlyToSelected({ target, insets }: { target: LatLon | null; insets: Insets }) {
  const map = useMap()
  useEffect(() => {
    if (!target) return
    const zoom = Math.max(map.getZoom(), 15)
    // Put the point in the middle of the visible part of the map, not behind the overlay.
    const shifted = map.project([target.lat, target.lon], zoom).subtract([insets.left / 2, -insets.bottom / 2])
    map.flyTo(map.unproject(shifted, zoom), zoom, { duration: 0.6 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, target?.lat, target?.lon])
  return null
}

/**
 * Open requests as approximate areas, plus the volunteer's home point. The list is the accessible alternative.
 * On the volunteer page the map is the full-page background under a floating list, so it takes `insets`
 * for the space the list covers, and shows its own zoom control clear of it.
 */
export default function RequestsMap({
  requests,
  home,
  selectedId,
  onSelect,
  className = 'h-72 rounded-xl border border-line',
  note = true,
  background = false,
  insets = { left: 0, bottom: 0 },
}: {
  requests: HelpRequest[]
  home: LatLon | null
  selectedId: string | null
  onSelect: (id: string) => void
  className?: string
  note?: boolean
  background?: boolean
  insets?: Insets
}) {
  const shown = requests.filter((r) => r.display_location)
  const points = [...shown.map((r) => r.display_location as LatLon), ...(home ? [home] : [])]
  const selected = shown.find((r) => r.id === selectedId)?.display_location ?? null

  return (
    <div className={note ? 'space-y-2' : 'h-full'}>
      <MapView
        center={home ?? undefined}
        zoom={12}
        className={className}
        label="Map of open requests near you"
        wheelZoom={background}
        zoomPosition={background ? 'bottomright' : 'topleft'}
      >
        <FitTo points={points} fitKey={shown.map((r) => r.id).join(',') + (home ? 'h' : '')} insets={insets} />
        <FlyToSelected target={selected} insets={insets} />
        {home && (
          <Marker position={[home.lat, home.lon]} icon={HOME_ICON}>
            <Tooltip>Your home location</Tooltip>
          </Marker>
        )}
        {shown.map((r) => {
          const c = r.display_location as LatLon
          const isSelected = r.id === selectedId
          return (
            <Circle
              key={r.id}
              center={[c.lat, c.lon]}
              radius={AREA_RADIUS_M}
              pathOptions={{ color: '#047857', fillColor: '#10b981', fillOpacity: isSelected ? 0.55 : 0.28, weight: isSelected ? 3 : 1.5 }}
              eventHandlers={{ click: () => onSelect(r.id) }}
            >
              <Tooltip>{r.text.length > 70 ? `${r.text.slice(0, 70)}…` : r.text}</Tooltip>
            </Circle>
          )
        })}
      </MapView>
      {note && (
        <p className="text-sm text-ink-soft">
          Circles show an approximate area (about 500 m). Exact addresses are shared only with the volunteer who takes the request.
        </p>
      )}
    </div>
  )
}
