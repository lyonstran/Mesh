import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Reveal from '../components/Reveal'
import { stagger } from '../lib/motion'

// Every claim on this page describes something that is built. Keep it that way (CLAUDE.md: describe only what exists).

const SITUATIONS = [
  'Power outages',
  'Flooding',
  'Heat waves',
  'Fallen trees and debris',
  'Smoke and air quality',
  'Groceries and medicine',
  'Checking on someone',
]

/** Small line icons (24px grid, stroke only) so the page needs no icon library. */
function Icon({ children }: { children: ReactNode }) {
  return (
    <span className="flex size-11 items-center justify-center rounded-xl bg-brand-tint text-brand-strong">
      <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        {children}
      </svg>
    </span>
  )
}

const FEATURES: { title: string; body: string; icon: ReactNode }[] = [
  {
    title: 'Ask in your own words',
    body: 'Type it or say it, in your own language. “My mom’s oxygen machine needs power” is all it takes.',
    icon: (
      <>
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      </>
    ),
  },
  {
    title: 'AI that understands the need',
    body: 'Mesh’s AI sorts each request by type of help and urgency, and writes a one-line summary for volunteers. It can raise urgency, never lower it.',
    icon: <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z" />,
  },
  {
    title: 'Matched on what matters',
    body: 'Volunteers see requests ranked by how well their skills fit, how close they are, and how urgent the need is, with a breakdown of why.',
    icon: (
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1" />
      </>
    ),
  },
  {
    title: 'Aware of conditions',
    body: 'Live National Weather Service alerts and local conditions like heat and air quality help put the most pressing requests first.',
    icon: <path d="M7 18a4 4 0 0 1-.5-8A6 6 0 0 1 18 9a4.5 4.5 0 0 1-.5 9zM13 11l-2 4h3l-2 4" />,
  },
  {
    title: 'Find each other',
    body: 'Once a volunteer is on the way, you can both share your live location, only with each other, until the request is done.',
    icon: (
      <>
        <path d="M12 21s-7-6.1-7-11.5A7 7 0 0 1 19 9.5C19 14.9 12 21 12 21z" />
        <circle cx="12" cy="9.5" r="2.5" />
      </>
    ),
  },
  {
    title: 'Private by design',
    body: 'Other volunteers only ever see an approximate area. Your exact location, name and details go only to the person helping you.',
    icon: (
      <>
        <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z" />
        <path d="M9 12l2 2 4-4" />
      </>
    ),
  },
]

const REQUESTER_STEPS = [
  { title: 'Tell us what’s wrong', body: 'Say or type it, and drop a pin where you are.' },
  { title: 'Check how we read it', body: 'See the type of help and urgency before it goes out. Fix anything we got wrong.' },
  { title: 'Get matched', body: 'A nearby volunteer with the ability to help picks it up, and a private chat opens.' },
  { title: 'Receive help', body: 'Wait for your volunteer and get help.' },
]

const VOLUNTEER_STEPS = [
  { title: 'Say what you can offer', body: 'Skills, tools, a vehicle, a generator, or just your time.' },
  { title: 'Set how far you’ll go', body: 'Choose your home area and a travel radius up to 15 km.' },
  { title: 'Pick a request', body: 'The best fits come first, with the distance and why it was ranked there.' },
  { title: 'Help, then close it out', body: 'Help your neighbor, and mark it resolved.' },
]

function Steps({ title, tone, steps }: { title: string; tone: 'brand' | 'ink'; steps: typeof REQUESTER_STEPS }) {
  const badge = tone === 'brand' ? 'bg-brand text-ink' : 'bg-ink text-white'
  return (
    <div className="rounded-2xl border border-line bg-surface p-6 sm:p-8">
      <h3 className="text-xl font-extrabold">{title}</h3>
      <ol className="mt-6 space-y-5">
        {steps.map((s, i) => (
          <li key={s.title} className="flex gap-4">
            <span className={`flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-extrabold ${badge}`}>{i + 1}</span>
            <div>
              <p className="font-semibold">{s.title}</p>
              <p className="mt-0.5 text-ink-soft">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

function FactorBar({ label, detail, value }: { label: string; detail: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="font-semibold">{label}</span>
        <span className="text-ink-soft">{detail}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-brand-soft">
        <div className="animate-grow-x h-full origin-left rounded-full bg-brand" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

/** What a volunteer sees: an AI-triaged request, why it ranks first, and the match. Illustrative, so it says "Example". */
function ProductPreview() {
  return (
    <figure aria-label="Example of a matched request" className="relative mx-auto w-full max-w-md lg:mx-0">
      <div aria-hidden className="absolute -inset-6 -z-10 rounded-[2.5rem] bg-gradient-to-br from-brand-tint via-transparent to-transparent blur-2xl" />
      <div className="animate-rise stagger rounded-2xl border border-line bg-surface p-5 shadow-[0_24px_48px_-24px_rgba(30,42,71,0.35)]" style={stagger(1)}>
        <div className="flex items-center justify-between">
          <figcaption className="text-xs font-semibold tracking-wide text-ink-soft uppercase">Example request</figcaption>
          <span className="text-xs text-ink-soft">about 1 km away · 3 min ago</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full bg-warn-soft px-2.5 py-1 text-xs font-bold text-warn">Urgency 4 of 5</span>
          <span className="rounded-full bg-brand-soft px-2.5 py-1 text-xs font-semibold text-brand-strong">Power</span>
          <span className="rounded-full bg-ground px-2.5 py-1 text-xs font-semibold text-ink-soft">Relies on a medical device</span>
        </div>
        <p className="mt-3 text-lg leading-snug font-semibold">Needs power for an oxygen concentrator after an overnight outage.</p>
        <p className="mt-1 text-sm text-ink-soft">“The electricity has been out since last night and my oxygen machine needs power.”</p>

        <div className="mt-5 rounded-xl bg-ground p-4">
          <p className="text-xs font-bold tracking-wide text-ink-soft uppercase">Why it’s your top match</p>
          <div className="mt-3 space-y-3">
            <FactorBar label="Skills fit" detail="generator, power banks" value={86} />
            <FactorBar label="Distance" detail="about 1 km" value={78} />
            <FactorBar label="Need" detail="urgent, medical device" value={90} />
          </div>
        </div>
      </div>

      <div
        className="animate-rise stagger relative mx-4 -mt-3 flex items-center gap-3 rounded-2xl bg-ink p-4 text-white shadow-[0_20px_40px_-20px_rgba(30,42,71,0.6)] sm:mx-8"
        style={stagger(3)}
      >
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-brand font-extrabold text-ink" aria-hidden>
          J
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Janelle is on her way</p>
          <p className="truncate text-sm text-white/70">Bringing a portable generator</p>
        </div>
        <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-300">
          <span className="size-2 animate-pulse rounded-full bg-emerald-300" aria-hidden />
          Live
        </span>
      </div>
    </figure>
  )
}

const primaryCta =
  'inline-flex min-h-12 items-center justify-center rounded-xl bg-brand px-6 text-lg font-semibold text-ink shadow-[0_8px_20px_-8px_rgba(16,185,129,0.8)] transition duration-150 hover:bg-emerald-400 active:scale-[0.98]'
const secondaryCta =
  'inline-flex min-h-12 items-center justify-center rounded-xl border border-line bg-surface px-6 text-lg font-semibold transition duration-150 hover:border-brand-strong active:scale-[0.98]'

export default function Landing() {
  return (
    <main className="relative isolate overflow-x-clip">
      {/* Decorative: a soft glow and a faint dot grid behind the hero. */}
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[44rem] bg-[radial-gradient(55%_60%_at_80%_10%,var(--color-brand-tint),transparent)]" />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[44rem] bg-[radial-gradient(var(--color-line)_1px,transparent_1px)] [background-size:22px_22px] [mask-image:linear-gradient(to_bottom,black,transparent)] opacity-60"
      />

      <section className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-12 pb-16 sm:pt-16 lg:min-h-[calc(100svh-4rem-1px)] lg:grid-cols-[1.05fr_1fr] lg:py-12">
        <div>
          <h1 className="animate-rise stagger mt-6 text-[2.6rem] leading-[1.05] font-extrabold tracking-tight sm:text-6xl" style={stagger(1)}>
            Your neighbors can help. <span className="text-brand-strong">Mesh finds the right one.</span>
          </h1>
          <p className="animate-rise stagger mt-6 max-w-xl text-lg text-ink-soft sm:text-xl" style={stagger(2)}>
            When the power’s out, the water’s rising or you just can’t do it alone, ask in your own words. Mesh works out what you
            need and how urgent it is, then connects you with a nearby volunteer who has the ability to help.
          </p>
          <div className="animate-rise stagger mt-8 flex flex-col gap-3 sm:flex-row" style={stagger(3)}>
            <Link to="/login" className={primaryCta}>
              Ask for help
            </Link>
            <Link to="/login" className={secondaryCta}>
              Become a volunteer
            </Link>
          </div>
          <ul className="animate-rise stagger mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink-soft" style={stagger(4)}>
            <li className="flex items-center gap-1.5">
              <Check /> Free to use
            </li>
            <li className="flex items-center gap-1.5">
              <Check /> Multilingual
            </li>
            <li className="flex items-center gap-1.5">
              <Check /> Your exact location stays private
            </li>
          </ul>
        </div>
        <ProductPreview />
      </section>

      <section aria-labelledby="situations-title" className="border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-8">
          <h2 id="situations-title" className="text-sm font-semibold text-ink-soft">
            For the moments when a neighbor can make the difference
          </h2>
          {/* Conveyor belt: two identical halves slide left by exactly one half, so the loop is seamless. Each half repeats
              the list so it is wider than the screen. Screen readers get the first list only; hover pauses it, and
              reduced-motion users get a still, wrapped list (index.css). */}
          <div className="marquee group mt-4 overflow-hidden">
            <div className="marquee-track flex w-max group-hover:[animation-play-state:paused]">
              {[0, 1].map((half) => (
                <ul key={half} aria-hidden={half === 1 || undefined} className="flex shrink-0 gap-2 pr-2">
                  {[...SITUATIONS, ...SITUATIONS].map((s, i) => (
                    <li
                      key={i}
                      aria-hidden={i >= SITUATIONS.length || undefined}
                      className="rounded-full border border-line bg-ground px-3.5 py-1.5 text-sm font-semibold whitespace-nowrap"
                    >
                      {s}
                    </li>
                  ))}
                </ul>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="scroll-mt-20">
        <Reveal className="mx-auto max-w-6xl px-4 py-20">
          <div className="max-w-2xl">
            <p className="font-semibold text-brand-strong">What Mesh does</p>
            <h2 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">Everything between “I need help” and “I’m on my way.”</h2>
          </div>
          <ul className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <li key={f.title} className="rounded-2xl border border-line bg-surface p-6 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_16px_32px_-20px_rgba(30,42,71,0.4)]">
                <Icon>{f.icon}</Icon>
                <h3 className="mt-5 text-lg font-extrabold">{f.title}</h3>
                <p className="mt-2 text-ink-soft">{f.body}</p>
              </li>
            ))}
          </ul>
        </Reveal>
      </section>

      <section id="how-it-works" className="scroll-mt-20 bg-surface/60">
        <Reveal className="mx-auto max-w-6xl px-4 py-20">
          <div className="max-w-2xl">
            <p className="font-semibold text-brand-strong">How it works</p>
            <h2 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">Two sides, one app.</h2>
            <p className="mt-3 text-lg text-ink-soft">One account can do both: ask for help one day, volunteer the next.</p>
          </div>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            <Steps title="When you need help" tone="brand" steps={REQUESTER_STEPS} />
            <Steps title="When you can help" tone="ink" steps={VOLUNTEER_STEPS} />
          </div>
        </Reveal>
      </section>

      <section id="safety" className="on-dark scroll-mt-20 bg-ink text-white">
        <Reveal className="mx-auto max-w-6xl px-4 py-20">
          <p className="font-semibold text-emerald-300">Safety and privacy</p>
          <h2 className="mt-2 max-w-2xl text-3xl font-extrabold tracking-tight sm:text-4xl">Built for trust, from the first message.</h2>
          <ul className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ['Emergencies go to 911', 'If a request sounds life-threatening, Mesh shows a “Call 911” screen before anything is sent. Mesh is not an emergency service.'],
              ['Approximate until matched', 'Other volunteers see only an area about 500 m across, never your address.'],
              ['Private conversations', 'Only you and the one volunteer helping you can read your chat.'],
              ['Location sharing you control', 'Live location is opt-in, shared with one person, and stops when the request ends.'],
            ].map(([title, body]) => (
              <li key={title} className="border-t border-white/15 pt-5">
                <p className="font-semibold text-emerald-300">{title}</p>
                <p className="mt-2 text-white/75">{body}</p>
              </li>
            ))}
          </ul>
        </Reveal>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20">
        <Reveal className="relative overflow-hidden rounded-3xl bg-brand-tint px-6 py-12 text-center sm:px-12">
          <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Help is closer than you think.</h2>
          <p className="mx-auto mt-3 max-w-xl text-lg text-ink-soft">Sign in with Google to ask for help or to start volunteering. It takes about a minute.</p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Link to="/login" className={primaryCta}>
              Ask for help
            </Link>
            <Link to="/login" className={secondaryCta}>
              Become a volunteer
            </Link>
          </div>
        </Reveal>
      </section>
    </main>
  )
}

function Check() {
  return (
    <svg viewBox="0 0 20 20" className="size-4 text-brand-strong" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 10.5l4 4 8-9" />
    </svg>
  )
}
