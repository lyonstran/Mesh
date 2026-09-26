import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import type { Health } from './lib/types'

// M0 placeholder: confirms the dev proxy and backend are wired up. Routing arrives in M1.
export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<Health>('/api/health') })

  return (
    <main className="mx-auto min-h-screen max-w-md bg-white px-4 py-8 text-slate-900">
      <h1 className="text-3xl font-bold">Mesh</h1>
      <p className="mt-1 text-slate-600">Neighbors helping neighbors after severe weather.</p>

      <section className="mt-6 rounded-lg border border-slate-200 p-4 text-sm">
        <h2 className="font-semibold">System status</h2>
        {health.isPending && <p className="mt-2 text-slate-500">Checking…</p>}
        {health.isError && <p className="mt-2 text-red-600">API unreachable: {health.error.message}</p>}
        {health.data && (
          <dl className="mt-2 grid grid-cols-2 gap-y-1">
            <dt>API</dt>
            <dd>{health.data.ok ? 'ok' : 'error'}</dd>
            <dt>Database</dt>
            <dd className={health.data.db === 'ok' ? 'text-green-700' : 'text-red-600'}>{health.data.db}</dd>
            <dt>LLM provider</dt>
            <dd>{health.data.llm_provider}</dd>
            <dt>Simulation</dt>
            <dd>{health.data.sim_active ? 'active' : 'off'}</dd>
          </dl>
        )}
      </section>
    </main>
  )
}
