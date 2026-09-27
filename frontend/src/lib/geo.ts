import type { LatLon } from './types'

/** HackGT venue (PLAN.md §0): where empty maps open, and the demo data's center. */
export const VENUE: LatLon = { lat: 33.7756, lon: -84.3963 }

const EARTH_RADIUS_KM = 6371.0088

/** Great-circle distance in km between two points. */
export function haversineKm(a: LatLon, b: LatLon): number {
  const rad = (d: number) => (d * Math.PI) / 180
  const dLat = rad(b.lat - a.lat)
  const dLon = rad(b.lon - a.lon)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h))
}

/** "350 m" under a kilometre (rounded to 10 m), otherwise "1.4 km". */
export function formatDistance(km: number): string {
  return km < 1 ? `${Math.max(10, Math.round((km * 1000) / 10) * 10)} m` : `${km.toFixed(1)} km`
}
