import { useEffect, useRef } from 'react'
import { Button } from './ui'

/** Full-screen 911 prompt shown before an emergency request is submitted (PLAN.md §9.2 step 5). */
export default function EmergencyInterstitial({
  onContinue,
  onBack,
  busy,
}: {
  onContinue: () => void
  onBack: () => void
  busy: boolean
}) {
  const callRef = useRef<HTMLAnchorElement>(null)
  useEffect(() => {
    callRef.current?.focus()
  }, [])

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="emergency-title"
      aria-describedby="emergency-body"
      className="fixed inset-0 z-50 flex flex-col bg-alert px-6 py-10 text-white"
    >
      <div className="mx-auto flex w-full max-w-xl flex-1 flex-col">
        <h1 id="emergency-title" className="text-4xl leading-tight font-extrabold">
          This sounds like an emergency. Call 911 now.
        </h1>
        <p id="emergency-body" className="mt-4 text-lg text-white/90">
          Mesh volunteers are neighbors, not emergency responders. If anyone's life is in danger, 911 is the fastest way
          to get help.
        </p>
        <a
          ref={callRef}
          href="tel:911"
          className="mt-10 flex min-h-16 items-center justify-center rounded-xl bg-white text-2xl font-extrabold text-alert"
        >
          Call 911
        </a>
        <div className="mt-auto space-y-3 pt-10">
          <Button variant="quiet" className="w-full border-white/60 bg-transparent text-white hover:border-white" onClick={onContinue} disabled={busy}>
            {busy ? 'Sending…' : 'Also send my request to Mesh volunteers'}
          </Button>
          <button type="button" onClick={onBack} className="min-h-11 w-full font-semibold text-white/90 underline underline-offset-4">
            Go back and edit
          </button>
        </div>
      </div>
    </div>
  )
}
