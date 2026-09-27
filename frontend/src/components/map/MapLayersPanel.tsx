import { useRef, useState } from 'react'
import { type LayerKey, type Layers, HEAT_MAX_ZOOM, TRACT_MIN_ZOOM } from '../../lib/mapLayers'
import { ALERT_COLORS, EJI_BAND_FILL, alertKey } from '../../lib/hazardColors'
import { EJI_BAND_TEXT } from '../../lib/labels'
import { NEED_TIERS, PIN_COLORS } from '../../lib/needTier'
import type { EjiBand, HazardRegion } from '../../lib/types'

const BANDS: EjiBand[] = ['Very high', 'High', 'Moderate', 'Lower']
const BAND_INDEX: Record<EjiBand, number> = { Unknown: 0, Lower: 1, Moderate: 2, High: 3, 'Very high': 4 }

function Swatch({ fill, stroke, round = false }: { fill: string; stroke?: string; round?: boolean }) {
  return (
    <span
      aria-hidden
      className={`size-3 shrink-0 border ${round ? 'rounded-full' : 'rounded-sm'}`}
      style={{ background: fill, borderColor: stroke ?? 'rgba(30,42,71,.25)' }}
    />
  )
}

/** A small copy of the map pin for the legend. */
function Pin({ fill, height, label }: { fill: string; height: number; label?: string }) {
  const width = Math.round((height * 32) / 42)
  return (
    <svg width={width} height={height} viewBox="0 0 32 42" aria-hidden className="shrink-0">
      <path
        d="M16 1.5C8 1.5 1.5 7.9 1.5 15.8c0 10.2 12.6 23.2 13.6 24.2a1.3 1.3 0 0 0 1.8 0c1-1 13.6-14 13.6-24.2C30.5 7.9 24 1.5 16 1.5z"
        fill={fill}
        stroke="#fff"
        strokeWidth="2"
      />
      {label && (
        <text x="16" y="16" dy="0.35em" textAnchor="middle" fill="#fff" style={{ font: "800 16px 'Atkinson Hyperlegible Next', system-ui, sans-serif" }}>
          {label}
        </text>
      )}
    </svg>
  )
}

function Toggle({ label, detail, on, onClick, disabled }: { label: string; detail?: string; on: boolean; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onClick}
      disabled={disabled}
      className="flex w-full cursor-pointer items-center gap-3 px-3 py-1.5 text-left hover:bg-brand-soft disabled:cursor-default disabled:opacity-60"
    >
      <span aria-hidden className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${on ? 'bg-brand-strong' : 'bg-line'}`}>
        <span className={`absolute top-0.5 size-4 rounded-full bg-white shadow transition-transform ${on ? 'translate-x-4' : 'translate-x-0.5'}`} />
      </span>
      <span className="min-w-0">
        <span className="block font-semibold">{label}</span>
        {detail && <span className="block text-xs text-ink-soft">{detail}</span>}
      </span>
    </button>
  )
}

/**
 * Top-right panel: what the markers mean, the three optional layers, and the clickable NWS alert list.
 * Picking an alert reports how much of the map the panel covers, so the fitted area lands beside or below it.
 */
export default function MapLayersPanel({
  layers,
  onToggle,
  region,
  zoom,
  selectedAlert,
  onPickAlert,
}: {
  layers: Layers
  onToggle: (key: LayerKey) => void
  region: HazardRegion | undefined
  zoom: number
  selectedAlert: string | null
  onPickAlert: (key: string, coveredPx: { top: number; right: number }) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(() => window.innerWidth >= 640) // collapsed by default on phones
  const covered = () => {
    const el = box.current
    const parent = el?.offsetParent as HTMLElement | null
    if (!el || !parent) return { top: 0, right: 0 }
    // Beside the panel when there's room next to it (wide screens); otherwise below it (phones).
    return parent.clientWidth - el.offsetWidth > 2 * el.offsetWidth ? { top: 0, right: el.offsetWidth + 12 } : { top: el.offsetHeight + 12, right: 0 }
  }

  const drawn = (region?.features ?? []).map((f, i) => ({ alert: f, key: alertKey(f, i) })).filter((x) => x.alert.geometry)
  const simulatedCount = drawn.filter((x) => x.alert.properties.source === 'Simulation').length
  const alertDetail = !region
    ? 'Loading'
    : region.sources_failed.length > 0
      ? "Couldn't reach NWS"
      : drawn.length === 0
        ? 'None active in Georgia'
        : `${drawn.length} active in Georgia${simulatedCount ? `, ${simulatedCount} simulated` : ''}`

  return (
    <div
      ref={box}
      className="absolute top-3 right-3 z-[500] w-80 max-w-[calc(100%-1.5rem)] overflow-hidden rounded-lg bg-surface/95 text-sm shadow-md ring-1 ring-ink/10"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center justify-between px-3 py-2 font-extrabold"
      >
        <span>Map layers</span>
        <span className="text-ink-soft" aria-hidden>
          {open ? '▴' : '▾'}
        </span>
      </button>

      {open && (
        <div className="max-h-[60vh] overflow-y-auto border-t border-line pb-1">
          <section aria-label="What the pins mean" className="space-y-1.5 px-3 py-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Requests</p>
            <ul className="space-y-1.5">
              <li className="flex items-center gap-2">
                <Pin fill={PIN_COLORS.default.fill} height={18} label="1" />
                Number = rank in your list
              </li>
              <li className="flex items-center gap-2">
                <span className="flex items-end gap-0.5">
                  {[...NEED_TIERS].reverse().map((t) => (
                    <Pin key={t.tier} fill={PIN_COLORS.default.fill} height={Math.round(t.pinHeight * 0.45)} />
                  ))}
                </span>
                Bigger pin = more need
              </li>
              <li className="flex items-center gap-2">
                <Pin fill={PIN_COLORS.emergency.fill} height={18} />
                Red: may be an emergency
              </li>
            </ul>
          </section>

          <div className="border-t border-line py-1">
            <Toggle label="Weather alerts" detail={alertDetail} on={layers.alerts} onClick={() => onToggle('alerts')} />
            {layers.alerts && drawn.length > 0 && (
              <ul aria-label="NWS alerts" className="mx-3 mb-1 max-h-40 overflow-y-auto rounded-md ring-1 ring-line">
                {drawn.map(({ alert, key }) => {
                  const p = alert.properties
                  const selected = key === selectedAlert
                  return (
                    <li key={key}>
                      <button
                        type="button"
                        onClick={() => onPickAlert(key, covered())}
                        aria-pressed={selected}
                        className={`flex w-full cursor-pointer items-start gap-2 px-2 py-1.5 text-left hover:bg-brand-soft ${selected ? 'bg-brand-soft' : ''}`}
                      >
                        <span className="mt-1">
                          <Swatch fill={ALERT_COLORS[p.level].fill} stroke={ALERT_COLORS[p.level].stroke} />
                        </span>
                        <span className="min-w-0">
                          <span className="block font-semibold">
                            {p.event}
                            {p.source === 'Simulation' && (
                              <span className="ml-1 rounded bg-alert px-1 py-0.5 align-middle text-[10px] font-extrabold tracking-wide text-white">SIM</span>
                            )}
                          </span>
                          {p.area_desc && <span className="block truncate text-xs text-ink-soft">{p.area_desc}</span>}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}

            <Toggle
              label="Area vulnerability"
              detail={layers.vulnerability && zoom < TRACT_MIN_ZOOM ? 'Zoom in to see census tracts' : 'CDC EJI 2024, by census tract'}
              on={layers.vulnerability}
              onClick={() => onToggle('vulnerability')}
            />
            {layers.vulnerability && (
              <ul className="mx-3 mb-1 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                {BANDS.map((b) => (
                  <li key={b} className="flex items-center gap-2">
                    <Swatch fill={EJI_BAND_FILL[BAND_INDEX[b]]} />
                    {EJI_BAND_TEXT[b].replace(' area', '')}
                  </li>
                ))}
              </ul>
            )}

            <Toggle
              label="Need heatmap"
              detail={layers.heat && zoom > HEAT_MAX_ZOOM ? 'Zoom out to see hotspots' : 'Where the most urgent requests cluster'}
              on={layers.heat}
              onClick={() => onToggle('heat')}
            />
          </div>
        </div>
      )}
    </div>
  )
}
