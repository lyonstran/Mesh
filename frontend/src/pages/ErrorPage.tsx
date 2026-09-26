import { Link } from 'react-router-dom'

export default function ErrorPage() {
  return (
    <main className="mx-auto max-w-xl px-4 py-16">
      <h1 className="text-3xl font-extrabold">This page hit a problem</h1>
      <p className="mt-3 text-ink-soft">Reload to try again. If it keeps happening, go back home and retry from there.</p>
      <Link to="/" className="mt-6 inline-block font-semibold underline underline-offset-4">
        Back home
      </Link>
    </main>
  )
}
