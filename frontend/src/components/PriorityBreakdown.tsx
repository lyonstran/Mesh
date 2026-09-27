import { useId } from 'react'
import { EJI_BAND_TEXT, HAZARD_LEVEL_LABELS, MATCH_FACTOR_LABELS, MATCH_FLAG_TEXT, URGENCY_LABELS } from '../lib/labels'
import type { MatchFactor, NeedPart } from '../lib/types'

const pct = (n: number) => `${Math.round(n * 100)}%`

function needPartText(part: NeedPart): { label: string; value: string } {
  switch (part.key) {
    case 'urgency':
      return { label: 'Urgency', value: `${part.raw} of 5, ${URGENCY_LABELS[part.raw]?.toLowerCase() ?? ''}` }
    case 'hazard':
      return {
        label: 'Weather hazard here',
        value: `${HAZARD_LEVEL_LABELS[part.raw] ?? `Level ${part.raw}`} (level ${part.raw} of 3)${part.simulated ? ', SIMULATED scenario' : ''}`,
      }
    case 'wait':
      return { label: 'Waiting', value: part.raw >= 60 ? 'over an hour' : `${Math.round(part.raw)} min` }
    case 'eji':
      return { label: 'Area', value: `${EJI_BAND_TEXT[part.band]} (CDC EJI 2024)` }
  }
}

function FactorRow({ factor }: { factor: MatchFactor }) {
  const labelId = useId() // unique even with several cards' panels open
  return (
    <li className="space-y-1">
      <p className="font-semibold" id={labelId}>
        {MATCH_FACTOR_LABELS[factor.key]}
      </p>
      {/* Bars only on screen; screen readers get the value from the meter role. */}
      <div
        role="meter"
        aria-labelledby={labelId}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(factor.value * 100)}
        className="h-2 overflow-hidden rounded-full bg-brand-tint ring-1 ring-brand-strong/30 ring-inset"
      >
        <div className="h-full rounded-full bg-brand" style={{ width: pct(factor.value) }} />
      </div>
      <p className="text-xs text-ink-soft">{factor.source}</p>
      {factor.flag && <p className="text-xs font-semibold text-ink">{MATCH_FLAG_TEXT[factor.flag]}</p>}
      {factor.detail && (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-lg bg-ground/60 px-3 py-2 text-sm">
          {factor.detail.map((part) => {
            const { label, value } = needPartText(part)
            return (
              <div key={part.key} className="contents">
                <dt className="text-ink-soft">{label}</dt>
                <dd>{value}</dd>
              </div>
            )
          })}
        </dl>
      )}
    </li>
  )
}

/** "Why this rank?": each factor of the blended score as a bar, with its source (team plan P1-5). */
export default function PriorityBreakdown({ breakdown, note }: { breakdown: MatchFactor[]; note: string }) {
  return (
    <div className="space-y-3 rounded-xl border border-line bg-surface p-4 text-sm">
      <ul className="space-y-4">
        {breakdown.map((f) => (
          <FactorRow key={f.key} factor={f} />
        ))}
      </ul>
      <p className="border-t border-line pt-2 text-xs text-ink-soft">{note}</p>
    </div>
  )
}
