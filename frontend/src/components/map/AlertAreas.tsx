import { useEffect, useRef } from 'react'
import { GeoJSON, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { ALERT_COLORS, alertKey } from '../../lib/hazardColors'
import { HAZARD_LEVEL_LABELS } from '../../lib/labels'
import type { HazardRegion, RegionAlert } from '../../lib/types'

/** Map padding (px) that keeps a fitted area clear of the floating panels. */
export interface FitPadding {
  topLeft: [number, number]
  bottomRight: [number, number]
}

/** A picked alert. `n` changes on every pick, so picking the same alert again still flies back to it. */
export interface AlertSelection {
  key: string
  n: number
}

function until(iso: string | null): string | null {
  if (!iso) return null
  return `Until ${new Date(iso).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}`
}

function AlertArea({ alert, selection, padding }: { alert: RegionAlert; selection: number | null; padding: FitPadding }) {
  const map = useMap()
  const layer = useRef<L.GeoJSON>(null)
  const selected = selection !== null
  const color = ALERT_COLORS[alert.properties.level]

  useEffect(() => {
    const target = layer.current
    if (selection === null || !target || !alert.geometry) return
    // Fit the whole area into the visible part of the map, then open its popup once the map settles.
    // Opening it first would let the popup's own auto-pan fight the fly animation.
    const open = () => target.openPopup()
    map.once('moveend', open)
    map.flyToBounds(L.geoJSON(alert.geometry).getBounds(), {
      paddingTopLeft: padding.topLeft,
      paddingBottomRight: padding.bottomRight,
      maxZoom: 11,
      duration: 0.8,
    })
    return () => {
      map.off('moveend', open)
    }
    // Re-run on each pick of this alert, not when padding changes mid-flight.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, selection])

  if (!alert.geometry) return null
  return (
    <GeoJSON
      ref={layer}
      data={alert.geometry}
      style={{
        color: color.stroke,
        fillColor: color.fill,
        fillOpacity: selected ? 0.3 : 0.16,
        weight: selected ? 3 : 1.5,
        dashArray: alert.properties.level === 1 ? '4 3' : undefined,
      }}
    >
      <Popup>
        <div className="max-w-64 space-y-1 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
            {alert.properties.source === 'Simulation' ? 'SIMULATED scenario' : 'NWS (official)'} · {HAZARD_LEVEL_LABELS[alert.properties.level]}
          </p>
          <p className="font-extrabold">{alert.properties.event}</p>
          {alert.properties.headline && <p>{alert.properties.headline}</p>}
          {until(alert.properties.expires) && <p className="text-ink-soft">{until(alert.properties.expires)}</p>}
        </div>
      </Popup>
    </GeoJSON>
  )
}

/** Active NWS alert areas, drawn under the request circles. Popups render NWS text as React text, never as HTML. */
export default function AlertAreas({
  region,
  selection,
  padding,
}: {
  region: HazardRegion
  selection: AlertSelection | null
  padding: FitPadding
}) {
  return (
    <>
      {region.features.map((alert, i) => {
        const key = alertKey(alert, i)
        return (
          <AlertArea
            // GeoJSON layers don't update in place; a new key per fetch redraws them.
            key={`${region.fetched_at}-${key}`}
            alert={alert}
            selection={selection?.key === key ? selection.n : null}
            padding={padding}
          />
        )
      })}
    </>
  )
}
