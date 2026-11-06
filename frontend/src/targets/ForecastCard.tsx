import { formatDate } from './formatDate'
import type { Forecast } from './types'

// The goal date. All dates and the wording come from the backend; this only lays them out.
export function ForecastCard({ forecast }: { forecast: Forecast }) {
  const ready = forecast.status === 'ready' && forecast.earliest && forecast.likely && forecast.latest
  if (!ready) {
    return (
      <section aria-label="Goal date" className="rounded-2xl bg-surface p-4 shadow-sm">
        <h2 className="text-base font-bold text-ink">Goal date</h2>
        <p className="mt-1 text-sm text-muted">{forecast.message}</p>
      </section>
    )
  }
  const weekly = forecast.weekly_change_kg === null ? null : Math.abs(forecast.weekly_change_kg)
  return (
    <section aria-label="Goal date" className="rounded-2xl bg-surface p-4 shadow-sm">
      <h2 className="text-base font-bold text-ink">Goal date</h2>
      <p className="mt-1 text-sm text-ink-soft">
        {forecast.current_weight_kg} kg → {forecast.target_weight_kg} kg
      </p>
      <p className="mt-2 font-display text-2xl font-bold text-brand-strong">{formatDate(forecast.likely!)}</p>
      <p className="text-sm text-ink-soft">
        Most likely, about {forecast.weeks_likely} weeks from now. Anywhere from {formatDate(forecast.earliest!)} to{' '}
        {formatDate(forecast.latest!)}.
      </p>
      {weekly !== null && (
        <p className="mt-1 text-xs text-muted">About {weekly} kg a week if you follow your plan fully.</p>
      )}
      {forecast.note && <p className="mt-2 text-xs text-muted">{forecast.note}</p>}
    </section>
  )
}
