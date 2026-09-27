import { lazy, Suspense, type ComponentProps } from 'react'

// Leaflet is about 150 KB; load it only on pages that show a map so the first paint stays fast on phones.
const Picker = lazy(() => import('./LocationPicker'))
const Requests = lazy(() => import('./RequestsMap'))
const Volunteers = lazy(() => import('./VolunteersMap'))
const Live = lazy(() => import('./LiveMap'))

function MapFallback({ className }: { className: string }) {
  return <div aria-hidden className={`animate-pulse bg-line/60 ${className}`} />
}

export function LocationPicker(props: ComponentProps<typeof Picker>) {
  return (
    <Suspense fallback={<MapFallback className="h-56 rounded-xl" />}>
      <Picker {...props} />
    </Suspense>
  )
}

export function RequestsMap(props: ComponentProps<typeof Requests>) {
  return (
    <Suspense fallback={<MapFallback className={props.className ?? 'h-72 rounded-xl'} />}>
      <Requests {...props} />
    </Suspense>
  )
}

export function LiveMap(props: ComponentProps<typeof Live>) {
  return (
    <Suspense fallback={<MapFallback className="h-72 rounded-xl" />}>
      <Live {...props} />
    </Suspense>
  )
}

export function VolunteersMap(props: ComponentProps<typeof Volunteers>) {
  return (
    <Suspense fallback={<MapFallback className="h-64 rounded-xl" />}>
      <Volunteers {...props} />
    </Suspense>
  )
}
