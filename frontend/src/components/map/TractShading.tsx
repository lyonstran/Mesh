import { useState } from 'react'
import { GeoJSON, Pane, useMapEvents } from 'react-leaflet'
import { type Bbox, useTracts } from '../../api/hooks'
import { EJI_BAND_FILL } from '../../lib/hazardColors'
import type { TractBandFeature } from '../../lib/types'

/** Faint EJI vulnerability shading by census tract for the visible area, drawn under everything else. */
export default function TractShading() {
  const map = useMapEvents({
    moveend: () => setView(read()),
  })
  const read = () => {
    const b = map.getBounds()
    return { bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()] as Bbox, zoom: map.getZoom() }
  }
  const [view, setView] = useState(read)
  const tracts = useTracts(view.bbox, view.zoom, true)
  const data = tracts.data
  if (!data || data.features.length === 0) return null
  return (
    // A pane below the overlay pane keeps the shading under alert areas and request markers; it never takes clicks.
    <Pane name="tracts" style={{ zIndex: 350, pointerEvents: 'none' }}>
      <GeoJSON
        key={`${view.zoom}-${data.features.length}-${view.bbox.join(',')}`}
        data={{ type: 'FeatureCollection', features: data.features } as GeoJSON.FeatureCollection}
        interactive={false}
        style={(f) => ({
          fillColor: EJI_BAND_FILL[(f as TractBandFeature).properties.band_index],
          fillOpacity: 0.32,
          color: '#ffffff',
          weight: 0.5,
          opacity: 0.6,
        })}
      />
    </Pane>
  )
}
