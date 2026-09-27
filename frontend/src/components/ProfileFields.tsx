import { useRef, useState } from 'react'
import { LANGUAGES, RESOURCE_LABELS, SKILL_LABELS } from '../lib/labels'
import {
  MAX_CUSTOM_SKILL_LENGTH,
  MAX_CUSTOM_SKILLS,
  MAX_RADIUS_KM,
  RESOURCES,
  SKILLS,
  type HelperProfile,
  type RequesterFlags,
  type Role,
  type Skill,
} from '../lib/types'
import type { Basics } from '../lib/profile'
import { Field, inputClass } from './ui'

// Form sections shared by onboarding and the profile page.

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item]
}

const chipBase = 'inline-flex min-h-11 items-center cursor-pointer rounded-full border px-4 text-sm font-semibold transition-colors duration-200'
const chipOn = 'border-gray-400 bg-gray-200 text-ink'
const chipOff = 'border-line bg-surface text-ink hover:border-emerald-600'

function Chip({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: string }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onClick} className={`${chipBase} ${selected ? chipOn : chipOff}`}>
      {children}
    </button>
  )
}

/** `role` tailors the hint on onboarding; the profile page omits it because these fields are shared by both profiles. */
export function BasicsFields({ role, value, onChange }: { role?: Role; value: Basics; onChange: (v: Basics) => void }) {
  return (
    <div className="space-y-5">
      <Field label="Your name">
        <input className={inputClass} value={value.name} onChange={(e) => onChange({ ...value, name: e.target.value })} maxLength={80} required />
      </Field>
      <Field label="Language you're most comfortable in">
        <select className={inputClass} value={value.language} onChange={(e) => onChange({ ...value, language: e.target.value })}>
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label="About you"
        hint={
          role === 'helper'
            ? 'Your work or experience, in a sentence or two.'
            : role === 'requester'
              ? 'Anything a volunteer should know about you or your household.'
              : 'Your work or experience, or anything a volunteer should know about you or your household.'
        }
      >
        <textarea
          className={`${inputClass} min-h-24`}
          value={value.background}
          onChange={(e) => onChange({ ...value, background: e.target.value })}
          maxLength={1000}
        />
      </Field>
    </div>
  )
}

/** "+ Add your own" pill that opens an inline text field for skills not in the list. */
function CustomSkillAdder({ value, onChange }: { value: HelperProfile; onChange: (v: HelperProfile) => void }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [note, setNote] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const pillRef = useRef<HTMLButtonElement>(null)
  const atLimit = value.custom_skills.length >= MAX_CUSTOM_SKILLS

  const close = () => {
    setOpen(false)
    setDraft('')
    setNote(null)
    requestAnimationFrame(() => pillRef.current?.focus())
  }

  const add = () => {
    const skill = draft.split(/\s+/).filter(Boolean).join(' ')
    if (!skill) return close()
    // Typed one of the listed skills? Select that chip instead of adding a duplicate.
    const listed = SKILLS.find((s) => SKILL_LABELS[s].toLowerCase() === skill.toLowerCase())
    let added = false
    if (listed) {
      if (!value.skills.includes(listed)) onChange({ ...value, skills: [...value.skills, listed] })
      setNote(`“${SKILL_LABELS[listed]}” is already in the list, so we selected it.`)
    } else if (value.custom_skills.some((s) => s.toLowerCase() === skill.toLowerCase())) {
      setNote(`You already added “${skill}”.`)
    } else {
      onChange({ ...value, custom_skills: [...value.custom_skills, skill] })
      setNote(null)
      added = true
    }
    setDraft('')
    if (added && value.custom_skills.length + 1 >= MAX_CUSTOM_SKILLS) close()
    else inputRef.current?.focus()
  }

  if (!open) {
    if (atLimit) return <p className="text-sm text-ink-soft">You've added the maximum of {MAX_CUSTOM_SKILLS} of your own skills.</p>
    return (
      <button
        ref={pillRef}
        type="button"
        onClick={() => {
          setOpen(true)
          requestAnimationFrame(() => inputRef.current?.focus())
        }}
        className={`${chipBase} border-dashed border-ink-soft bg-transparent text-ink hover:border-ink hover:bg-surface`}
      >
        + Add your own
      </button>
    )
  }

  return (
    <div className="w-full">
      <label htmlFor="custom-skill" className="sr-only">
        Your own skill
      </label>
      <div className="flex gap-2">
        <input
          id="custom-skill"
          ref={inputRef}
          className={inputClass}
          value={draft}
          maxLength={MAX_CUSTOM_SKILL_LENGTH}
          placeholder="e.g. Tree climbing"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault() // don't submit the surrounding form
              add()
            } else if (e.key === 'Escape') {
              e.preventDefault()
              close()
            }
          }}
        />
        <button type="button" onClick={add} className="min-h-12 shrink-0 rounded-lg bg-ink px-4 font-semibold text-white hover:bg-ink/90">
          Add
        </button>
        <button type="button" onClick={close} className="min-h-12 shrink-0 rounded-lg px-3 font-semibold text-ink-soft hover:text-ink">
          Done
        </button>
      </div>
      <p className="mt-1 text-sm text-ink-soft" aria-live="polite">
        {note ?? 'Press Enter to add it. You can add several.'}
      </p>
    </div>
  )
}

export function HelperProfileFields({ value, onChange }: { value: HelperProfile; onChange: (v: HelperProfile) => void }) {
  return (
    <div className="space-y-6">
      <fieldset>
        <legend className="font-semibold">Skills</legend>
        <div className="mt-3 flex flex-wrap gap-2">
          {SKILLS.map((s: Skill) => (
            <Chip key={s} selected={value.skills.includes(s)} onClick={() => onChange({ ...value, skills: toggle(value.skills, s) })}>
              {SKILL_LABELS[s]}
            </Chip>
          ))}
          {value.custom_skills.map((s) => (
            <span key={s} className={`${chipBase} ${chipOn} gap-1 pr-1`}>
              {s}
              <button
                type="button"
                aria-label={`Remove ${s}`}
                onClick={() => onChange({ ...value, custom_skills: value.custom_skills.filter((x) => x !== s) })}
                className="flex size-8 items-center justify-center rounded-full cursor-pointer text-lg leading-none text-ink hover:bg-ink/10"
              >
                ×
              </button>
            </span>
          ))}
          <CustomSkillAdder value={value} onChange={onChange} />
        </div>
      </fieldset>
      <fieldset>
        <legend className="font-semibold">Things you can bring</legend>
        <div className="mt-3 flex flex-wrap gap-2">
          {RESOURCES.map((r) => (
            <Chip key={r} selected={value.resources.includes(r)} onClick={() => onChange({ ...value, resources: toggle(value.resources, r) })}>
              {RESOURCE_LABELS[r]}
            </Chip>
          ))}
        </div>
      </fieldset>
      <Field
        label="What can you offer?"
        hint="In your own words. This is what we match against requests, so be specific: “I can cut up fallen trees and haul debris in my truck.”"
      >
        <textarea
          className={`${inputClass} min-h-28`}
          value={value.about}
          onChange={(e) => onChange({ ...value, about: e.target.value })}
          maxLength={1000}
        />
      </Field>
      <Field label="How far will you travel?" hint="Measured from your home location.">
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={1}
            max={MAX_RADIUS_KM}
            step={1}
            value={value.radius_km}
            onChange={(e) => onChange({ ...value, radius_km: Number(e.target.value) })}
            className="w-full accent-emerald-600"
          />
          <span className="w-16 shrink-0 text-right font-semibold">{value.radius_km} km</span>
        </div>
      </Field>
      <label className="flex items-start gap-3 rounded-lg bg-surface p-3">
        <input
          type="checkbox"
          className="mt-1 size-5 shrink-0 accent-emerald-600"
          checked={value.show_area_to_requesters}
          onChange={(e) => onChange({ ...value, show_area_to_requesters: e.target.checked })}
        />
        <span>
          <span className="font-semibold">Show my approximate area to people asking for help nearby</span>
          <span className="mt-0.5 block text-sm text-ink-soft">
            They see a circle about 500 m across around your home location, never your name, address or skills.
          </span>
        </span>
      </label>
    </div>
  )
}

const FLAG_LABELS: Record<keyof RequesterFlags, string> = {
  medical_device: 'I rely on a medical device that needs power',
  mobility: 'I have limited mobility',
  lives_alone: 'I live alone',
}

export function RequesterFlagsFields({ value, onChange }: { value: RequesterFlags; onChange: (v: RequesterFlags) => void }) {
  return (
    <fieldset>
      <legend className="font-semibold">Anything that affects the help you need?</legend>
      <p className="mt-1 text-sm text-ink-soft">Optional. Only the volunteer who picks your request will see this.</p>
      <div className="mt-3 space-y-2">
        {(Object.keys(FLAG_LABELS) as (keyof RequesterFlags)[]).map((key) => (
          <label key={key} className="flex min-h-11 items-center gap-3 rounded-lg bg-surface px-3">
            <input
              type="checkbox"
              className="size-5 accent-emerald-600"
              checked={value[key]}
              onChange={(e) => onChange({ ...value, [key]: e.target.checked })}
            />
            {FLAG_LABELS[key]}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
