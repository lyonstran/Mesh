import { useEffect, useMemo, useState } from 'react'
import { Circle, Marker, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { useHazardRegion } from '../../api/hooks'
import { needValue } from '../../lib/needTier'
import type { LatLon, RankedRequest } from '../../lib/types'
import AlertAreas, { type AlertSelection } from './AlertAreas'
import { HOME_ICON } from './icons'
import { HEAT_MAX_ZOOM, TRACT_MIN_ZOOM, useLayers } from '../../lib/mapLayers'
import MapLayersPanel from './MapLayersPanel'
import MapView from './MapView'
import NeedHeat from './NeedHeat'
import RequestMarker from './RequestMarker'
import TractShading from './TractShading'

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

function ZoomWatch({ onZoom }: { onZoom: (z: number) => void }) {
  const map = useMapEvents({ zoomend: () => onZoom(map.getZoom()) })
  useEffect(() => onZoom(map.getZoom()), [map, onZoom])
  return null
}

/**
 * The volunteer map: ranked requests as numbered pins colored by need, the volunteer's home and travel radius,
 * and optional layers (NWS alert areas, EJI tract shading, need heatmap). The list is the accessible alternative.
 * The map is the full-page background under a floating list, so it takes `insets` for the space the list covers.
 */
export default function RequestsMap({
  requests,
  home,
  radiusKm,
  selectedId,
  hoveredId,
  onSelect,
  onHover,
  onClaim,
  claimBusy,
  weightsNote,
  className = 'h-72 rounded-xl border border-line',
  note = true,
  background = false,
  insets = { left: 0, bottom: 0 },
  showAlerts = false,
}: {
  requests: RankedRequest[] // in rank order; pins are numbered to match the list
  home: LatLon | null
  radiusKm: number | null
  selectedId: string | null
  hoveredId: string | null
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
  onClaim: (id: string) => void
  claimBusy: boolean
  weightsNote: string
  className?: string
  note?: boolean
  background?: boolean
  insets?: Insets
  showAlerts?: boolean // statewide NWS alert areas (volunteer map only)
}) {
  const [layers, toggleLayer] = useLayers()
  const region = useHazardRegion(showAlerts && layers.alerts)
  const [zoom, setZoom] = useState(12)
  const [alertPick, setAlertPick] = useState<AlertSelection | null>(null)
  const [panelCover, setPanelCover] = useState({ top: 0, right: 0 })
  // Keep a fitted alert clear of the list panel (left or bottom) and of the layers panel (top-right).
  const alertPadding = {
    topLeft: [insets.left + EDGE_PX, panelCover.top + EDGE_PX] as [number, number],
    bottomRight: [panelCover.right + EDGE_PX, insets.bottom + EDGE_PX] as [number, number],
  }

  // An opened request popup stays clear of the list panel (left or bottom) and the layers panel (top-right).
  const wide = insets.left > 0
  const popupPadding = {
    topLeft: [insets.left + 16, wide ? 16 : 72] as [number, number],
    bottomRight: [wide ? 352 : 16, insets.bottom + 16] as [number, number],
  }

  const ranked = requests.map((r, i) => ({ request: r, rank: i + 1 })).filter((x) => x.request.display_location)
  const points = [...ranked.map((x) => x.request.display_location as LatLon), ...(home ? [home] : [])]
  const selected = ranked.find((x) => x.request.id === selectedId)?.request.display_location ?? null
  const heatPoints = useMemo(
    () =>
      ranked.map(({ request }) => {
        const p = request.display_location as LatLon
        return [p.lat, p.lon, needValue(request.breakdown)] as [number, number, number]
      }),
    // Rebuild only when the set of requests or their need changes, not on every poll.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ranked.map((x) => `${x.request.id}:${needValue(x.request.breakdown).toFixed(2)}`).join(',')],
  )

  return (
    <div className={`relative ${note ? 'space-y-2' : 'h-full'}`}>
      {showAlerts && (
        <MapLayersPanel
          layers={layers}
          onToggle={toggleLayer}
          region={region.data}
          zoom={zoom}
          selectedAlert={alertPick?.key ?? null}
          onPickAlert={(key, cover) => {
            setPanelCover(cover)
            setAlertPick((prev) => ({ key, n: (prev?.n ?? 0) + 1 }))
          }}
        />
      )}
      <MapView
        center={home ?? undefined}
        zoom={12}
        className={className}
        label="Map of open requests near you"
        wheelZoom={background}
        zoomPosition={background ? 'bottomright' : 'topleft'}
      >
        <ZoomWatch onZoom={setZoom} />
        <FitTo points={points} fitKey={ranked.map((x) => x.request.id).join(',') + (home ? 'h' : '')} insets={insets} />
        <FlyToSelected target={selected} insets={insets} />
        {layers.vulnerability && zoom >= TRACT_MIN_ZOOM && <TractShading />}
        {showAlerts && layers.alerts && region.data && <AlertAreas region={region.data} selection={alertPick} padding={alertPadding} />}
        {layers.heat && zoom <= HEAT_MAX_ZOOM && heatPoints.length > 0 && <NeedHeat points={heatPoints} />}
        {home && radiusKm && (
          <Circle
            center={[home.lat, home.lon]}
            radius={radiusKm * 1000}
            interactive={false}
            pathOptions={{ color: '#1e2a47', weight: 1.5, dashArray: '6 6', fill: false, opacity: 0.55 }}
          />
        )}
        {home && (
          <Marker position={[home.lat, home.lon]} icon={HOME_ICON}>
            <Tooltip>{radiusKm ? `Your home. Dashed ring: the ${radiusKm} km you'll travel.` : 'Your home location'}</Tooltip>
          </Marker>
        )}
        {ranked.map(({ request, rank }) => (
          <RequestMarker
            key={request.id}
            request={request}
            rank={rank}
            selected={request.id === selectedId}
            hovered={request.id === hoveredId}
            zoom={zoom}
            weightsNote={weightsNote}
            panPadding={popupPadding}
            onSelect={() => onSelect(request.id)}
            onHover={(on) => onHover(on ? request.id : null)}
            onClaim={() => onClaim(request.id)}
            claimBusy={claimBusy}
          />
        ))}
      </MapView>
      {note && (
        <p className="text-sm text-ink-soft">
          Pins mark an approximate area (about 500 m). Exact addresses are shared only with the volunteer who takes the request.
        </p>
      )}
    </div>
  )
}
