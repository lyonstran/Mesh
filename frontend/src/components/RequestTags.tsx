import { CATEGORY_LABELS, FLAG_LABELS, URGENCY_LABELS } from '../lib/labels'
import type { HelpRequest } from '../lib/types'

// Urgency reads by colour and words together, never colour alone. Red stays reserved for 5 (life in danger).
const URGENCY_STYLE: Record<number, string> = {
  1: 'bg-ground text-ink-soft ring-1 ring-line',
  2: 'bg-ground text-ink-soft ring-1 ring-line',
  3: 'bg-brand-soft text-brand-strong',
  4: 'bg-warn-soft text-warn',
  5: 'bg-alert/10 text-alert',
}

/** Urgency, type of help and (for the two participants) vulnerability flags, from triage. Renders nothing before triage. */
export function RequestTags({ request, showFlags = false }: { request: HelpRequest; showFlags?: boolean }) {
  const { urgency, category } = request
  const flags = showFlags ? (request.flags ?? []) : []
  if (!urgency && !category && flags.length === 0) return null
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="About this request">
      {urgency ? (
        <li className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${URGENCY_STYLE[urgency] ?? URGENCY_STYLE[1]}`}>
          Urgency {urgency} of 5<span className="font-semibold"> · {URGENCY_LABELS[urgency]}</span>
        </li>
      ) : null}
      {category && (
        <li className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand-strong">{CATEGORY_LABELS[category]}</li>
      )}
      {flags.map((f) => (
        <li key={f} className="rounded-full bg-ground px-2.5 py-0.5 text-xs font-semibold text-ink-soft ring-1 ring-line">
          {FLAG_LABELS[f]}
        </li>
      ))}
    </ul>
  )
}

/**
 * The AI summary as the headline, with the person's own words underneath. Falls back to just their words when there's no
 * summary yet, or when the summary is only the first 120 characters of the text (the rules fallback).
 */
export function RequestText({ request, size = 'lg' }: { request: HelpRequest; size?: 'lg' | 'base' }) {
  const summary = request.summary?.trim()
  const useful = summary && !request.text.startsWith(summary)
  const main = size === 'lg' ? 'text-lg leading-snug' : 'leading-snug'
  if (!useful) return <p className={main}>{request.text}</p>
  return (
    <div>
      <p className={`${main} font-semibold`}>{summary}</p>
      <p className="mt-1 text-sm text-ink-soft">
        <span className="sr-only">In their words: </span>“{request.text}”
      </p>
    </div>
  )
}
