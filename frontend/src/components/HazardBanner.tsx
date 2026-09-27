import { useHazards } from '../api/hooks'
import { CATEGORY_LABELS, HAZARD_LABELS, HAZARD_LEVEL_LABELS } from '../lib/labels'
import type { Category, Hazard, HazardReport, LatLon } from '../lib/types'

// Level 0 gray, 1 yellow, 2 orange, 3 red (PLAN.md §7). A left stripe plus the level label, so color is never the only cue.
const LEVEL_STYLES: Record<number, { box: string; stripe: string; dot: string }> = {
  0: { box: 'bg-surface', stripe: 'border-slate-300', dot: 'bg-slate-400' },
  1: { box: 'bg-yellow-50', stripe: 'border-yellow-400', dot: 'bg-yellow-400' },
  2: { box: 'bg-orange-50', stripe: 'border-orange-500', dot: 'bg-orange-500' },
  3: { box: 'bg-red-50', stripe: 'border-red-600', dot: 'bg-red-600' },
}

function SourceTag({ hazard }: { hazard: Hazard }) {
  if (hazard.source === 'Simulation') {
    return <span className="rounded-full bg-alert px-2 py-0.5 text-xs font-extrabold tracking-wide text-white">SIMULATED</span>
  }
  return hazard.official ? (
    <span className="rounded-full bg-ink px-2 py-0.5 text-xs font-semibold text-white">NWS (official)</span>
  ) : (
    <span className="rounded-full border border-ink/25 px-2 py-0.5 text-xs font-semibold text-ink-soft">Open-Meteo (derived)</span>
  )
}

function describe(h: Hazard): string {
  if (h.official || (h.source === 'Simulation' && h.event)) return h.headline ?? h.event ?? HAZARD_LABELS[h.type]
  const reading = h.value !== null ? `${Math.round(h.value * 10) / 10} ${h.unit ?? ''}`.trim() : ''
  return [HAZARD_LABELS[h.type], reading, h.category].filter(Boolean).join(' · ')
}

function expiresText(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso)
  return `Until ${d.toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}`
}

function currentLine(report: HazardReport): string {
  const c = report.current
  const parts = [
    c.apparent_temperature_f != null && `Feels like ${Math.round(c.apparent_temperature_f)}°F`,
    c.wind_gust_mph != null && `gusts ${Math.round(c.wind_gust_mph)} mph`,
    c.us_aqi != null && `AQI ${Math.round(c.us_aqi)}`,
  ].filter(Boolean)
  return parts.join(' · ')
}

function needLabel(need: string): string {
  return CATEGORY_LABELS[need as Category] ?? need
}

/** Current hazards at a point: official NWS alerts first, derived Open-Meteo signals after. */
export default function HazardBanner({ point, className = '' }: { point: LatLon | null | undefined; className?: string }) {
  const hazards = useHazards(point)
  if (!point || hazards.isPending || hazards.error) return null
  const report = hazards.data
  const style = LEVEL_STYLES[report.level]
  const now = currentLine(report)

  return (
    <section
      aria-label="Weather and hazards near this location"
      aria-live="polite"
      className={`animate-fade-in rounded-xl border-l-4 p-4 ring-1 ring-ink/10 ${style.box} ${style.stripe} ${className}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={`size-2.5 shrink-0 rounded-full ${style.dot}`} aria-hidden />
        <h2 className="font-extrabold">{HAZARD_LEVEL_LABELS[report.level]}</h2>
        {report.simulated && (
          <span className="rounded-md bg-ink px-2 py-0.5 text-xs font-extrabold tracking-wider text-white">SIMULATED SCENARIO</span>
        )}
      </div>

      {report.hazards.length > 0 && (
        <ul className="mt-3 space-y-2">
          {report.hazards.map((h, i) => (
            <li key={`${h.source}-${h.type}-${i}`} className="text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <SourceTag hazard={h} />
                <span className="font-semibold">{describe(h)}</span>
              </div>
              {h.official && expiresText(h.expires) && <p className="mt-0.5 text-ink-soft">{expiresText(h.expires)}</p>}
              {h.official && h.instruction && (
                <details className="mt-1 text-ink-soft">
                  <summary className="cursor-pointer font-semibold text-ink">What NWS advises</summary>
                  <p className="mt-1 whitespace-pre-line">{h.instruction}</p>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}

      {report.likely_needs.length > 0 && (
        <p className="mt-3 text-sm">
          <span className="font-semibold">Likely needs: </span>
          {report.likely_needs.map(needLabel).join(', ')}
        </p>
      )}
      {now && <p className="mt-2 text-sm text-ink-soft">Now: {now}</p>}
      {report.sources_failed.length > 0 && (
        <p className="mt-2 text-sm text-ink-soft">Couldn't reach {report.sources_failed.join(' and ')}, so this may be incomplete.</p>
      )}
    </section>
  )
}
