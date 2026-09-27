import { useState } from 'react'
import { Marker, useMapEvents } from 'react-leaflet'
import { searchAddress } from '../../api/hooks'
import { ApiError } from '../../api/client'
import { VENUE } from '../../lib/geo'
import type { GeocodeMatch, LatLon } from '../../lib/types'
import { Button, inputClass } from '../ui'
import { BRAND_ICON } from './icons'
import MapView, { Recenter } from './MapView'

function ClickToPlace({ onPick }: { onPick: (p: LatLon) => void }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lon: e.latlng.lng }) })
  return null
}

function geolocationMessage(err: GeolocationPositionError): string {
  if (err.code === err.PERMISSION_DENIED) {
    return 'Location permission was blocked. Allow it in your browser settings, or search an address or tap the map instead.'
  }
  return "Couldn't get your location. Search an address or tap the map instead."
}

/**
 * Pick a point: use the device location, search a street address, or tap/drag a pin.
 * The map is a convenience; the two buttons work without it.
 */
export default function LocationPicker({
  value,
  onChange,
  clearable = false,
}: {
  value: LatLon | null
  onChange: (v: LatLon | null) => void
  clearable?: boolean
}) {
  const [query, setQuery] = useState('')
  const [matches, setMatches] = useState<GeocodeMatch[] | null>(null)
  const [busy, setBusy] = useState<'gps' | 'search' | null>(null)
  const [note, setNote] = useState<string | null>(null)

  const useMyLocation = () => {
    setNote(null)
    if (!('geolocation' in navigator)) {
      setNote('This browser can’t share your location. Search an address or tap the map instead.')
      return
    }
    setBusy('gps')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setBusy(null)
        setMatches(null)
        onChange({ lat: pos.coords.latitude, lon: pos.coords.longitude })
      },
      (err) => {
        setBusy(null)
        setNote(geolocationMessage(err))
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    )
  }

  const search = async (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim().length < 3) return
    setNote(null)
    setBusy('search')
    try {
      const { matches: found } = await searchAddress(query.trim())
      setMatches(found)
      if (found.length === 0) setNote('No match. Try a full street address with the city, or tap the map.')
    } catch (err) {
      setMatches(null)
      setNote(err instanceof ApiError ? err.message : "Couldn't search right now. Use your location or tap the map instead.")
    } finally {
      setBusy(null)
    }
  }

  const pick = (p: LatLon) => {
    setMatches(null)
    setNote(null)
    onChange(p)
  }

  return (
    <div className="space-y-3">
      <Button type="button" variant="quiet" className="w-full" onClick={useMyLocation} disabled={busy !== null}>
        {busy === 'gps' ? 'Finding you…' : 'Use my current location'}
      </Button>

      <form onSubmit={search} className="flex gap-2">
        <label htmlFor="address-search" className="sr-only">
          Search a street address
        </label>
        <input
          id="address-search"
          className={inputClass}
          placeholder="Street address, city (for example 225 North Ave NW, Atlanta)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          maxLength={200}
        />
        <Button type="submit" variant="quiet" className="shrink-0" disabled={busy !== null || query.trim().length < 3}>
          {busy === 'search' ? 'Searching…' : 'Find'}
        </Button>
      </form>

      {matches && matches.length > 0 && (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
          {matches.map((m) => (
            <li key={`${m.lat},${m.lon}`}>
              <button
                type="button"
                onClick={() => pick({ lat: m.lat, lon: m.lon })}
                className="min-h-11 w-full cursor-pointer px-3 py-2 text-left hover:bg-brand-soft"
              >
                {m.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      {note && (
        <p role="status" className="text-sm text-ink-soft">
          {note}
        </p>
      )}

      <MapView center={value ?? VENUE} zoom={value ? 16 : 11} className="h-56 rounded-xl border border-line" label="Map: tap to place a pin, drag it to adjust">
        <ClickToPlace onPick={pick} />
        {value && (
          <>
            <Recenter center={value} />
            <Marker
              position={[value.lat, value.lon]}
              icon={BRAND_ICON}
              draggable
              eventHandlers={{
                dragend: (e) => {
                  const p = (e.target as L.Marker).getLatLng()
                  onChange({ lat: p.lat, lon: p.lng })
                },
              }}
            />
          </>
        )}
      </MapView>

      <p className="flex items-center justify-between gap-3 text-sm text-ink-soft">
        <span>{value ? 'Pin set. Drag it to adjust.' : 'Tap the map to drop a pin.'}</span>
        {clearable && value && (
          <button type="button" onClick={() => onChange(null)} className="cursor-pointer font-semibold text-ink underline underline-offset-4">
            Remove
          </button>
        )}
      </p>
    </div>
  )
}
