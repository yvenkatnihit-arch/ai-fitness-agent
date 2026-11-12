import { useEffect, useState, type FormEvent } from 'react'

import { FormError, inputClass } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import type { WeightHistory } from './types'
import { WeightChart } from './WeightChart'

const kg = (n: number) => `${Math.abs(n)} kg`

const BACKFILL_DAYS = 60 // the same limit as the server (backend/app/workflows/weight_log.py)
const isoDay = (d: Date) => d.toLocaleDateString('en-CA') // YYYY-MM-DD in the person's own calendar
const daysAgo = (n: number) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return isoDay(d)
}
const shortDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

// What the numbers mean, in words (all values come from the server; this only phrases them).
function describe(h: WeightHistory): string[] {
  const lines: string[] = []
  if (h.change_since_start_kg !== null && h.change_since_start_kg !== 0) {
    lines.push(`${h.change_since_start_kg < 0 ? 'Down' : 'Up'} ${kg(h.change_since_start_kg)} since you started.`)
  }
  if (h.kg_to_target !== null) {
    lines.push(Math.abs(h.kg_to_target) < 0.5 ? 'You are at your target weight.' : `${kg(h.kg_to_target)} ${h.kg_to_target < 0 ? 'above' : 'below'} your target.`)
  }
  if (h.weekly_change_kg !== null) lines.push(`About ${kg(h.weekly_change_kg)} a week ${h.weekly_change_kg < 0 ? 'down' : 'up'} over this period.`)
  return lines
}

// The weight log on the dashboard: today's weigh-in, a small chart, and how far along you are. Not shown to users who must not see numbers.
export function WeightCard({ onChanged, onHistory }: { onChanged?: () => void; onHistory?: (history: WeightHistory) => void }) {
  const api = useApi()
  const [history, setHistory] = useState<WeightHistory | null>(null)
  const [draft, setDraft] = useState('')
  const [day, setDay] = useState(() => daysAgo(0)) // the weigh-in date: today unless changed
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    let cancelled = false
    api.get<WeightHistory>('/weight').then(
      (h) => { if (!cancelled) { setHistory(h); onHistory?.(h) } },
      () => { /* a bonus card: if it cannot load, the rest of Home still works */ },
    )
    return () => { cancelled = true }
  }, [api, onHistory])

  async function save(event: FormEvent) {
    event.preventDefault()
    const value = Number(draft)
    if (!draft.trim() || !Number.isFinite(value) || !day) return
    setBusy(true)
    setError(null)
    try {
      const today = daysAgo(0)
      const saved = await api.post<WeightHistory>('/weight', { weight_kg: value, ...(day !== today ? { measured_on: day } : {}) })
      setHistory(saved)
      onHistory?.(saved)
      setDraft('')
      setDay(today)
      onChanged?.() // the goal-date forecast starts from the latest weight, so it is refreshed
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  if (!history || history.numbers_hidden) return null
  const facts = describe(history)
  return (
    <section aria-label="Weight" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-bold text-ink">Weight</h2>
        {history.latest_kg !== null && <p className="text-sm text-ink-soft"><span className="text-xl font-bold text-ink">{history.latest_kg}</span> kg</p>}
      </div>
      <WeightChart entries={history.entries} target={history.target_weight_kg} />
      {history.percent_to_target !== null && (
        <div
          role="progressbar" aria-label="Progress to your target weight" aria-valuemin={0} aria-valuemax={100} aria-valuenow={history.percent_to_target}
          aria-valuetext={`${history.percent_to_target}% of the way to your target weight`} className="h-2.5 overflow-hidden rounded-full bg-surface-2"
        >
          <div className="h-full rounded-full bg-brand" style={{ width: `${history.percent_to_target}%` }} />
        </div>
      )}
      {facts.length > 0 && <ul className="flex flex-col gap-0.5 text-sm text-ink-soft">{facts.map((f) => <li key={f}>{f}</li>)}</ul>}
      <form onSubmit={save} className="flex items-end gap-2">
        <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-ink-soft">
          Weight (kg)
          <input
            type="number" inputMode="decimal" step="0.1" min="30" max="300" value={draft} onChange={(e) => setDraft(e.target.value)}
            className={inputClass} placeholder={history.latest_kg === null ? '' : String(history.latest_kg)}
          />
        </label>
        <label className="flex w-36 flex-col gap-1 text-xs font-medium text-ink-soft">
          Date
          <input type="date" value={day} min={daysAgo(BACKFILL_DAYS)} max={daysAgo(0)} onChange={(e) => setDay(e.target.value)} className={inputClass} />
        </label>
        <button
          type="submit" disabled={busy || !draft.trim() || !day}
          className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-on-brand disabled:opacity-50"
        >
          {busy ? 'Saving…' : day === daysAgo(0) ? 'Log weight' : `Log for ${shortDate(day)}`}
        </button>
      </form>
      <p className="text-xs text-muted">You can also add past weigh-ins (up to {BACKFILL_DAYS} days back) to see your trend. Weigh-ins show your trend and update your goal date. Your daily targets change when you update your weight in Settings.</p>
      {error && <FormError message={error.message} requestId={error.requestId} />}
    </section>
  )
}
