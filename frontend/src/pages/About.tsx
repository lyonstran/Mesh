/** Data sources and credits (team plan P3-4). Public, so it renders without the backend. */

const DATA_SOURCES: { name: string; by: string; use: string; href: string }[] = [
  {
    name: 'Environmental Justice Index 2024',
    by: 'CDC and ATSDR',
    use: 'How vulnerable each Georgia census tract is to environmental burden, one input to how requests are prioritized.',
    href: 'https://www.atsdr.cdc.gov/',
  },
  {
    name: 'TIGER/Line census tract boundaries (2020)',
    by: 'US Census Bureau',
    use: 'Which census tract a request falls in, so it can be matched to the index above.',
    href: 'https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html',
  },
  {
    name: 'Active weather alerts',
    by: 'National Weather Service',
    use: 'Official warnings and advisories for a request’s location.',
    href: 'https://www.weather.gov/',
  },
  {
    name: 'Weather forecast and air quality',
    by: 'Open-Meteo.com (CC BY 4.0)',
    use: 'Wind, heat, rain and air quality, used to flag conditions the official alerts may not cover.',
    href: 'https://open-meteo.com/',
  },
  {
    name: 'Map data',
    by: 'OpenStreetMap contributors',
    use: 'The map tiles on every map in Mesh.',
    href: 'https://www.openstreetmap.org/copyright',
  },
  {
    name: 'Address search',
    by: 'US Census Bureau Geocoder',
    use: 'Turning a street address into a point on the map.',
    href: 'https://geocoding.geo.census.gov/',
  },
]

const AI: { name: string; use: string }[] = [
  {
    name: 'Muse Spark by Meta',
    use: 'Reads each request to suggest a type of help, an urgency and a short summary, and rewrites requests and volunteer profiles so they can be matched. It never sets scores or lowers urgency.',
  },
  {
    name: 'all-MiniLM-L6-v2 (sentence-transformers, Apache 2.0)',
    use: 'Runs on our server to measure how closely a request fits a volunteer’s skills.',
  },
]

export default function About() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-3xl font-extrabold">Data sources and credits</h1>
      <p className="mt-3 text-ink-soft">
        Mesh is built on public data and open tools. Scores and distances are computed by our own code from these sources.
      </p>

      <h2 className="mt-10 text-xl font-extrabold">Data</h2>
      <ul className="mt-4 space-y-5">
        {DATA_SOURCES.map((s) => (
          <li key={s.name}>
            <a href={s.href} target="_blank" rel="noopener noreferrer" className="font-semibold underline underline-offset-4">
              {s.name}
            </a>
            <span className="text-ink-soft">, {s.by}</span>
            <p className="mt-1 text-ink-soft">{s.use}</p>
          </li>
        ))}
      </ul>

      <h2 className="mt-10 text-xl font-extrabold">AI</h2>
      <ul className="mt-4 space-y-5">
        {AI.map((a) => (
          <li key={a.name}>
            <p className="font-semibold">{a.name}</p>
            <p className="mt-1 text-ink-soft">{a.use}</p>
          </li>
        ))}
      </ul>

      <p className="mt-10 rounded-xl bg-surface p-4 text-sm text-ink-soft">
        Mesh is not an emergency service and doesn’t dispatch help. If anyone’s life is in danger, call 911.
      </p>
    </main>
  )
}
