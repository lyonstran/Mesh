import L from 'leaflet'

/** A round dot marker drawn with CSS, so there are no default-icon image paths for Vite to break. */
export function dotIcon(fill: string, ring = '#ffffff', size = 22): L.DivIcon {
  return L.divIcon({
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<span style="display:block;width:${size}px;height:${size}px;border-radius:9999px;background:${fill};border:3px solid ${ring};box-shadow:0 1px 4px rgba(30,42,71,.45)"></span>`,
  })
}

export const BRAND_ICON = dotIcon('#10b981')
export const HOME_ICON = dotIcon('#1e2a47')
