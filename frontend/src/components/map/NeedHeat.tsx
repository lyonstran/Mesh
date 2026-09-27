import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import './leafletGlobal'
import 'leaflet.heat'

// Site palette: pale mint for lower need, brand green, then deep green and navy ink where need concentrates.
const GRADIENT = { 0.2: '#d1fae5', 0.45: '#34d399', 0.7: '#047857', 1: '#1e2a47' }

/** A glow weighted by need at each request's approximate (fuzzed) point. `points` are [lat, lon, need 0-1]. */
export default function NeedHeat({ points }: { points: [number, number, number][] }) {
  const map = useMap()
  useEffect(() => {
    const layer = L.heatLayer(points, { radius: 38, blur: 28, max: 1, minOpacity: 0.25, maxZoom: 12, gradient: GRADIENT })
    layer.addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, points])
  return null
}
