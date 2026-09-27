import { useEffect, useMemo, useRef } from 'react'
import { Circle, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { URGENCY_LABELS } from '../../lib/labels'
import { PIN_COLORS, needTier, needValue } from '../../lib/needTier'
import type { LatLon, RankedRequest } from '../../lib/types'
import PriorityBreakdown from '../PriorityBreakdown'
import type { FitPadding } from './AlertAreas'

/** The fuzzed point is 300-500 m from the real one, so the circle shows an area, never an address. */
export const AREA_RADIUS_M = 500
const AREA_MIN_ZOOM = 14
const PIN_RATIO = 32 / 42 // width / height of the pin shape below

// A map pin (teardrop) with the rank number in its head. The tip sits on the request's approximate point.
function pinIcon(rank: number, height: number, colors: { fill: string; text: string }, pulse: boolean): L.DivIcon {
  const width = Math.round(height * PIN_RATIO)
  const digits = String(rank).length
  const fontSize = digits > 2 ? 10 : digits > 1 ? 12 : 14
  return L.divIcon({
    className: `mesh-pin${pulse ? ' mesh-pin-emergency' : ''}`,
    iconSize: [width, height],
    iconAnchor: [width / 2, height - 1],
    popupAnchor: [0, -height + 4],
    html: `<svg width="${width}" height="${height}" viewBox="0 0 32 42" aria-hidden="true" style="overflow:visible;filter:drop-shadow(0 2px 3px rgba(30,42,71,.4))">
      <path d="M16 1.5C8 1.5 1.5 7.9 1.5 15.8c0 10.2 12.6 23.2 13.6 24.2a1.3 1.3 0 0 0 1.8 0c1-1 13.6-14 13.6-24.2C30.5 7.9 24 1.5 16 1.5z" fill="${colors.fill}" stroke="#ffffff" stroke-width="2"/>
      <text x="16" y="16" dy="0.35em" text-anchor="middle" fill="${colors.text}" style="font:800 ${fontSize}px 'Atkinson Hyperlegible Next',system-ui,sans-serif">${rank}</text>
    </svg>`,
  })
}

/**
 * One ranked request on the volunteer map. Number = rank in the list; pin size = need tier; color = state
 * (navy, brand green when hovered or selected, red for a possible emergency). The approximate-area circle shows
 * when it's hovered or selected, or once zoomed in.
 */
export default function RequestMarker({
  request,
  rank,
  selected,
  hovered,
  zoom,
  weightsNote,
  panPadding,
  onSelect,
  onHover,
  onClaim,
  claimBusy,
}: {
  request: RankedRequest
  rank: number
  selected: boolean
  hovered: boolean
  zoom: number
  weightsNote: string
  panPadding: FitPadding // keeps an opened popup clear of the list panel and the layers panel
  onSelect: () => void
  onHover: (on: boolean) => void
  onClaim: () => void
  claimBusy: boolean
}) {
  const map = useMap()
  const point = request.display_location as LatLon
  const tier = needTier(needValue(request.breakdown))
  const active = selected || hovered
  const colors = active ? PIN_COLORS.active : request.emergency ? PIN_COLORS.emergency : PIN_COLORS.default
  const height = tier.pinHeight + (active ? 6 : 0)
  const icon = useMemo(() => pinIcon(rank, height, colors, request.emergency && !active), [rank, height, colors, request.emergency, active])
  const marker = useRef<L.Marker>(null)

  // Open the popup once the map has finished flying to the request. Opening it during the flight let the popup
  // hang off the top of the map; after the flight, auto-pan (with panPadding) can bring all of it into view.
  useEffect(() => {
    if (!selected) return
    const open = () => marker.current?.openPopup()
    const fallback = window.setTimeout(open, 900) // in case the map didn't need to move
    const onMoveEnd = () => {
      window.clearTimeout(fallback)
      open()
    }
    map.once('moveend', onMoveEnd)
    return () => {
      window.clearTimeout(fallback)
      map.off('moveend', onMoveEnd)
    }
  }, [map, selected])

  return (
    <>
      {(active || zoom >= AREA_MIN_ZOOM) && (
        <Circle
          center={[point.lat, point.lon]}
          radius={AREA_RADIUS_M}
          interactive={false}
          pathOptions={{ color: colors.fill, fillColor: colors.fill, fillOpacity: active ? 0.16 : 0.08, weight: active ? 2 : 1 }}
        />
      )}
      <Marker
        ref={marker}
        position={[point.lat, point.lon]}
        icon={icon}
        zIndexOffset={active ? 1000 : request.emergency ? 500 : -rank}
        keyboard
        title={`Request ${rank}: ${tier.label}${request.emergency ? ', may be an emergency' : ''}`}
        eventHandlers={{
          click: (e) => {
            // A newly picked request opens its popup after the fly-to (effect above), not mid-flight.
            if (!selected) e.target.closePopup()
            onSelect()
          },
          mouseover: () => onHover(true),
          mouseout: () => onHover(false),
        }}
      >
        <Popup
          className="mesh-popup"
          maxWidth={300}
          minWidth={250}
          autoPanPaddingTopLeft={panPadding.topLeft}
          autoPanPaddingBottomRight={panPadding.bottomRight}
        >
          <div className="space-y-2 text-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
              #{rank} · {tier.label}
              {request.distance_km !== null && ` · about ${request.distance_km < 1 ? 'under 1' : Math.round(request.distance_km)} km`}
            </p>
            <p className="line-clamp-3 font-semibold">{request.summary ?? request.text}</p>
            {request.urgency !== null && (
              <p className="text-ink-soft">
                Urgency {request.urgency} of 5: {URGENCY_LABELS[request.urgency]?.toLowerCase()}
              </p>
            )}
            {request.emergency && <p className="font-semibold text-alert">May be an emergency. The requester was shown the option to call 911.</p>}
            <PriorityBreakdown breakdown={request.breakdown} note={weightsNote} />
            <button
              type="button"
              onClick={onClaim}
              disabled={claimBusy}
              className="inline-flex min-h-10 w-full cursor-pointer items-center justify-center rounded-lg bg-brand px-4 font-semibold text-ink hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Help with this
            </button>
          </div>
        </Popup>
      </Marker>
    </>
  )
}
