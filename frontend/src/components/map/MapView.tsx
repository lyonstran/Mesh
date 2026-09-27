import 'leaflet/dist/leaflet.css'
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { MapContainer, TileLayer, useMap, ZoomControl } from 'react-leaflet'
import { VENUE } from '../../lib/geo'
import type { LatLon } from '../../lib/types'

// OpenStreetMap's standard tiles need the attribution below; VITE_MAP_TILE_URL swaps the provider (keep its attribution).
const TILE_URL = import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

/** Moves the map when `center` changes (for example after a search result is picked). */
export function Recenter({ center, zoom }: { center: LatLon; zoom?: number }) {
  const map = useMap()
  useEffect(() => {
    map.setView([center.lat, center.lon], zoom ?? map.getZoom())
  }, [map, center.lat, center.lon, zoom])
  return null
}

export default function MapView({
  center = VENUE,
  zoom = 14,
  className = 'h-64 rounded-xl border border-line',
  label,
  wheelZoom = false,
  zoomPosition = 'topleft',
  children,
}: {
  center?: LatLon
  zoom?: number
  className?: string
  label: string
  wheelZoom?: boolean // on for full-page maps, off inside scrolling pages so the wheel still scrolls
  zoomPosition?: 'topleft' | 'bottomright'
  children?: ReactNode
}) {
  return (
    // isolate keeps Leaflet's high z-indexes below the sticky header.
    <div className={`isolate overflow-hidden ${className}`} role="region" aria-label={label}>
      <MapContainer
        center={[center.lat, center.lon]}
        zoom={zoom}
        scrollWheelZoom={wheelZoom}
        zoomControl={zoomPosition === 'topleft'}
        className="h-full w-full"
      >
        {zoomPosition !== 'topleft' && <ZoomControl position={zoomPosition} />}
        <TileLayer url={TILE_URL} attribution={ATTRIBUTION} maxZoom={19} />
        {children}
      </MapContainer>
    </div>
  )
}
