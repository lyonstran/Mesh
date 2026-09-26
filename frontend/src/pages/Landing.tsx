import { Link } from 'react-router-dom'

const REQUESTER_STEPS = [
  { title: 'Sign in', body: 'Use your Google account and tell us a little about your household.' },
  { title: 'Say what you need', body: '“A tree fell across my driveway.” Plain words are enough.' },
  { title: 'Chat with your volunteer', body: 'When someone picks your request, a private chat opens between the two of you.' },
]

const VOLUNTEER_STEPS = [
  { title: 'Sign in', body: 'Use your Google account and pick “I can help.”' },
  { title: 'Describe what you can offer', body: 'Your skills, what you can bring, and in your own words what you can do.' },
  { title: 'Pick a request', body: 'See the requests that fit you best, choose one, and chat with the person directly.' },
]

function Steps({ title, steps }: { title: string; steps: typeof REQUESTER_STEPS }) {
  return (
    <div>
      <h3 className="text-xl font-extrabold">{title}</h3>
      <ol className="mt-4 space-y-4">
        {steps.map((s, i) => (
          <li key={s.title} className="flex gap-4">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink font-extrabold text-white">
              {i + 1}
            </span>
            <div>
              <p className="font-semibold">{s.title}</p>
              <p className="text-ink-soft">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

/** An illustration of the product's core moment: a request matched to a volunteer who fits. */
function ExampleMatch() {
  return (
    <figure className="rounded-2xl bg-surface p-5 shadow-[0_1px_0_var(--color-line),0_12px_32px_-16px_rgba(30,42,71,0.35)]">
      <figcaption className="text-sm font-semibold text-ink-soft">Example</figcaption>
      <div className="mt-3 flex gap-4">
        <div className="relative w-2 shrink-0 overflow-hidden rounded-full bg-porch-soft" aria-hidden>
          <div className="absolute inset-x-0 bottom-0 h-[85%] rounded-full bg-porch" />
        </div>
        <div>
          <p className="text-sm text-ink-soft">Request, posted 4 minutes ago</p>
          <p className="mt-1 text-lg">A tree fell across my driveway and I can't get my car out.</p>
        </div>
      </div>
      <div className="mt-5 rounded-xl bg-porch-soft p-4">
        <p className="font-semibold">Best fit: a neighbor with a chainsaw and a pickup truck</p>
        <p className="mt-1 text-ink-soft">“Happy to cut up fallen trees and haul away debris.”</p>
      </div>
    </figure>
  )
}

export default function Landing() {
  return (
    <main>
      <section className="mx-auto grid max-w-5xl gap-10 px-4 pt-12 pb-16 lg:grid-cols-[1.1fr_1fr] lg:items-center lg:pt-20">
        <div>
          <h1 className="text-[2.5rem] leading-[1.08] font-extrabold sm:text-6xl">Help from the neighbors around you, after the storm.</h1>
          <p className="mt-5 max-w-prose text-lg text-ink-soft">
            When severe weather hits, the fastest help is often next door. Mesh connects people who need a hand with
            volunteers whose skills fit what they need, then opens a private chat between them.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/login" className="inline-flex min-h-12 items-center rounded-lg bg-porch px-6 text-lg font-semibold text-ink hover:brightness-95">
              Ask for help
            </Link>
            <Link
              to="/login"
              className="inline-flex min-h-12 items-center rounded-lg border border-line bg-surface px-6 text-lg font-semibold hover:border-ink-soft"
            >
              Volunteer
            </Link>
          </div>
          <p className="mt-6 text-sm text-ink-soft">In a life-threatening emergency, call 911 first.</p>
        </div>
        <ExampleMatch />
      </section>

      <section id="how-it-works" className="scroll-mt-20 bg-surface">
        <div className="mx-auto max-w-5xl px-4 py-16">
          <h2 className="text-3xl font-extrabold">How it works</h2>
          <div className="mt-8 grid gap-12 md:grid-cols-2">
            <Steps title="If you need help" steps={REQUESTER_STEPS} />
            <Steps title="If you can help" steps={VOLUNTEER_STEPS} />
          </div>
        </div>
      </section>

      <section id="volunteering" className="mx-auto max-w-5xl scroll-mt-20 px-4 py-16">
        <h2 className="text-3xl font-extrabold">Requests ranked for you</h2>
        <div className="mt-4 max-w-prose space-y-4 text-lg text-ink-soft">
          <p>
            Volunteers don't scroll through every request. Mesh compares what you said you can offer with what each person
            asked for, and puts the closest matches first. Someone with a generator sees the person whose oxygen machine
            needs power; someone with a chainsaw sees the fallen tree.
          </p>
          <p>You always choose which request to take, and you can hand it back if plans change.</p>
        </div>
      </section>

      <section id="safety" className="scroll-mt-20 bg-ink text-white">
        <div className="mx-auto max-w-5xl px-4 py-16">
          <h2 className="text-3xl font-extrabold">Safety and privacy</h2>
          <ul className="mt-8 grid gap-8 md:grid-cols-3">
            <li>
              <p className="font-semibold text-porch">Not a replacement for 911</p>
              <p className="mt-2 text-white/80">
                If a request sounds like an emergency, Mesh shows a “Call 911” screen before anything is sent.
              </p>
            </li>
            <li>
              <p className="font-semibold text-porch">Private chats</p>
              <p className="mt-2 text-white/80">Only you and the one volunteer helping you can see your conversation.</p>
            </li>
            <li>
              <p className="font-semibold text-porch">Your details stay with your volunteer</p>
              <p className="mt-2 text-white/80">
                Other volunteers see only your request. Your name and anything you share about your needs go only to the
                person who picks it.
              </p>
            </li>
          </ul>
          <Link to="/login" className="mt-10 inline-flex min-h-12 items-center rounded-lg bg-porch px-6 font-semibold text-ink hover:brightness-95">
            Get started
          </Link>
        </div>
      </section>
    </main>
  )
}
