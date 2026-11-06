import { Link } from 'react-router'

import credits from './credits.json'

// "Data sources": credits the licences require (CoFID: Open Government Licence v3.0; USDA: please cite).
// The content is generated from data/sources.json by `uv run python -m fooddata.build`; don't edit credits.json by hand.
export function SourcesPage() {
  return (
    <main className="flex min-h-screen flex-col items-center bg-slate-50 px-4 py-8">
      <div className="flex w-full max-w-md flex-col gap-4">
        <header className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-900">Data sources</h1>
          <Link to="/" className="text-sm font-medium text-emerald-700">Back</Link>
        </header>
        <p className="text-sm text-slate-600">
          Our food nutrition values come from these public datasets. We thank the people who build and share them.
        </p>

        {credits.sources.map((s) => (
          <article key={s.key} className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">
              <a href={s.homepage} target="_blank" rel="noreferrer" className="underline decoration-slate-300">{s.name}</a>
            </h2>
            <p className="mt-1 text-xs text-slate-500">Release {s.release} · {s.foods} of our foods</p>
            <p className="mt-2 text-sm text-slate-700">{s.credit}</p>
            <p className="mt-2 text-xs text-slate-600">
              Licence:{' '}
              <a href={s.license_url} target="_blank" rel="noreferrer" className="text-emerald-700 underline">{s.license}</a>
            </p>
          </article>
        ))}

        {credits.recipes.map((r) => (
          <article key={r.key} className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">{r.name}</h2>
            <p className="mt-1 text-xs text-slate-500">{r.foods} of our foods</p>
            <p className="mt-2 text-sm text-slate-700">{r.description}</p>
          </article>
        ))}

        <ul className="flex list-disc flex-col gap-1 pl-5 text-xs text-slate-600">
          {credits.notes.map((note) => <li key={note}>{note}</li>)}
        </ul>
        <p className="text-xs text-slate-500">
          This app gives general guidance, not medical advice. Values are averages; real foods vary.
        </p>
      </div>
    </main>
  )
}
