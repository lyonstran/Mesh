// leaflet.heat is a classic plugin that extends the global `L`. Import this module before 'leaflet.heat'
// so the global exists (ES modules evaluate their imports in order).
import L from 'leaflet'

;(window as unknown as { L: typeof L }).L = L
