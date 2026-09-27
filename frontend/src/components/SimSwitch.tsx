import { useSetSim, useSim } from '../api/hooks'

/**
 * Demo-only disaster scenario switch in the header, plus the persistent SIMULATED SCENARIO badge while one is on
 * (CLAUDE.md rule 7). Renders nothing outside demo mode, where the sim endpoints are a 404.
 */
export default function SimSwitch() {
  const sim = useSim()
  const setSim = useSetSim()
  if (!sim.data) return null
  const { active, scenario_id, scenarios } = sim.data
  const current = scenarios.find((s) => s.id === scenario_id)
  const first = scenarios[0]
  if (!first) return null

  if (active) {
    return (
      <div className="flex items-center gap-2" role="status">
        <span
          className="rounded-md bg-alert px-2 py-1 text-xs font-extrabold tracking-wider whitespace-nowrap text-white"
          title={current ? `${current.title}. ${current.description}` : undefined}
        >
          SIMULATED<span className="hidden sm:inline"> SCENARIO</span>
        </span>
        <button
          type="button"
          onClick={() => setSim.mutate(null)}
          disabled={setSim.isPending}
          className="min-h-9 cursor-pointer rounded-md px-2 text-xs font-semibold whitespace-nowrap text-ink-soft underline underline-offset-4 hover:text-ink disabled:opacity-50"
        >
          {setSim.isPending ? 'Ending…' : 'End'}
        </button>
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={() => setSim.mutate(first.id)}
      disabled={setSim.isPending}
      title={`Demo only: ${first.title}. ${first.description}`}
      className="min-h-9 cursor-pointer rounded-md border border-dashed border-ink/30 px-2 text-xs font-semibold whitespace-nowrap text-ink-soft hover:border-ink hover:text-ink disabled:opacity-50"
    >
      {setSim.isPending ? 'Starting…' : (
        <>
          Simulate<span className="hidden sm:inline"> a storm</span>
        </>
      )}
    </button>
  )
}
