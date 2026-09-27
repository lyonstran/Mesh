import { useEffect, useRef, useState } from 'react'
import { Circle, Marker, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import { useHazardRegion } from '../../api/hooks'
import type { HazardRegion, HelpRequest, LatLon } from '../../lib/types'
import { ALERT_COLORS, alertKey } from '../../lib/hazardColors'
import AlertAreas, { type AlertSelection } from './AlertAreas'
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
 * Legend, show/hide switch and a list of the alerts. Picking one flies the map to its area.
 * Sits top-right, clear of the list panel and the zoom control.
 */
function AlertsControl({
  region,
  shown,
  onToggle,
  selectedKey,
  onPick,
}: {
  region: HazardRegion
  shown: boolean
  onToggle: () => void
  selectedKey: string | null
  onPick: (key: string, coveredPx: { top: number; right: number }) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  // How much of the map this control covers, so the fitted area lands beside or below it.
  const covered = () => {
    const el = box.current
    const parent = el?.offsetParent as HTMLElement | null
    if (!el || !parent) return { top: 0, right: 0 }
    // Beside the control when there's room next to it (wide screens); otherwise below it (phones).
    return parent.clientWidth - el.offsetWidth > 2 * el.offsetWidth ? { top: 0, right: el.offsetWidth + 12 } : { top: el.offsetHeight + 12, right: 0 }
  }
  const drawn = region.features.map((f, i) => ({ alert: f, key: alertKey(f, i) })).filter((x) => x.alert.geometry)
  const levels = [...new Set(drawn.map((x) => x.alert.properties.level))].sort()
  const label =
    region.sources_failed.length > 0
      ? "Couldn't reach NWS alerts"
      : drawn.length === 0
        ? 'No NWS alerts in Georgia'
        : `${drawn.length} NWS ${drawn.length === 1 ? 'alert' : 'alerts'} (official)`
  return (
    <div ref={box} className="absolute top-3 right-3 z-[500] w-80 max-w-[calc(100%-1.5rem)] overflow-hidden rounded-lg bg-surface/95 text-sm shadow-md ring-1 ring-ink/10">
      <div className="flex items-center gap-2 px-3 py-2">
        {levels.map((l) => (
          <span key={l} aria-hidden className="size-3 shrink-0 rounded-sm border" style={{ background: ALERT_COLORS[l].fill, borderColor: ALERT_COLORS[l].stroke }} />
        ))}
        <span className="flex-1 font-semibold">{label}</span>
        {drawn.length > 0 && (
          <button type="button" onClick={onToggle} aria-pressed={shown} className="cursor-pointer font-semibold text-brand-strong underline underline-offset-4">
            {shown ? 'Hide' : 'Show'}
          </button>
        )}
      </div>
      {shown && drawn.length > 0 && (
        <ul aria-label="NWS alerts" className="max-h-56 overflow-y-auto border-t border-line">
          {drawn.map(({ alert, key }) => {
            const p = alert.properties
            const selected = key === selectedKey
            return (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => onPick(key, covered())}
                  aria-pressed={selected}
                  className={`flex w-full cursor-pointer items-start gap-2 px-3 py-2 text-left hover:bg-brand-soft ${selected ? 'bg-brand-soft' : ''}`}
                >
                  <span aria-hidden className="mt-1 size-3 shrink-0 rounded-sm border" style={{ background: ALERT_COLORS[p.level].fill, borderColor: ALERT_COLORS[p.level].stroke }} />
                  <span className="min-w-0">
                    <span className="block font-semibold">{p.event}</span>
                    {p.area_desc && <span className="block truncate text-ink-soft">{p.area_desc}</span>}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
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
  showAlerts = false,
}: {
  requests: HelpRequest[]
  home: LatLon | null
  selectedId: string | null
  onSelect: (id: string) => void
  className?: string
  note?: boolean
  background?: boolean
  insets?: Insets
  showAlerts?: boolean // statewide NWS alert areas (volunteer map only)
}) {
  const region = useHazardRegion(showAlerts)
  const [alertsShown, setAlertsShown] = useState(true)
  const [alertPick, setAlertPick] = useState<AlertSelection | null>(null)
  const [legendCover, setLegendCover] = useState({ top: 0, right: 0 })
  // Keep a fitted alert clear of the list panel (left or bottom) and of the alerts legend (top-right).
  const alertPadding = {
    topLeft: [insets.left + EDGE_PX, legendCover.top + EDGE_PX] as [number, number],
    bottomRight: [legendCover.right + EDGE_PX, insets.bottom + EDGE_PX] as [number, number],
  }
  const shown = requests.filter((r) => r.display_location)
  const points = [...shown.map((r) => r.display_location as LatLon), ...(home ? [home] : [])]
  const selected = shown.find((r) => r.id === selectedId)?.display_location ?? null

  return (
    <div className={`relative ${note ? 'space-y-2' : 'h-full'}`}>
      {region.data && (
        <AlertsControl
          region={region.data}
          shown={alertsShown}
          onToggle={() => setAlertsShown((s) => !s)}
          selectedKey={alertPick?.key ?? null}
          onPick={(key, cover) => {
            setLegendCover(cover)
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
        <FitTo points={points} fitKey={shown.map((r) => r.id).join(',') + (home ? 'h' : '')} insets={insets} />
        <FlyToSelected target={selected} insets={insets} />
        {region.data && alertsShown && <AlertAreas region={region.data} selection={alertPick} padding={alertPadding} />}
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
