// Minimal types for the leaflet.heat plugin (it has none of its own).
import 'leaflet'

declare module 'leaflet' {
  interface HeatLayerOptions {
    minOpacity?: number
    maxZoom?: number
    max?: number
    radius?: number
    blur?: number
    gradient?: Record<number, string>
  }
  interface HeatLayer extends Layer {
    setLatLngs(latlngs: [number, number, number][]): this
    setOptions(options: HeatLayerOptions): this
  }
  function heatLayer(latlngs: [number, number, number][], options?: HeatLayerOptions): HeatLayer
}

declare module 'leaflet.heat'
