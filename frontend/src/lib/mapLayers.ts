import { useState } from 'react'

export type LayerKey = 'alerts' | 'vulnerability' | 'heat'
export type Layers = Record<LayerKey, boolean>

const STORAGE_KEY = 'mesh.mapLayers'
const DEFAULT_LAYERS: Layers = { alerts: true, vulnerability: false, heat: false }
export const TRACT_MIN_ZOOM = 8
export const HEAT_MAX_ZOOM = 12

/** Layer toggles remembered per browser. Storage can be missing or blocked, so every access is guarded. */
export function useLayers(): [Layers, (key: LayerKey) => void] {
  const [layers, setLayers] = useState<Layers>(() => {
    try {
      return { ...DEFAULT_LAYERS, ...JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') }
    } catch {
      return DEFAULT_LAYERS
    }
  })
  const toggle = (key: LayerKey) =>
    setLayers((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        // not remembered, still works
      }
      return next
    })
  return [layers, toggle]
}
