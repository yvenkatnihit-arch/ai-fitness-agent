import { useEffect, useState } from 'react'

import { FormError, PageShell } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import type { EvalResult, Insights, Usage } from './types'

// Costs here are usually fractions of a cent, so below one dollar four decimals are shown; rounding $0.0123 to "$0.01" would hide it.
const money = (usd: number) => (usd === 0 ? '$0' : usd < 1 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`)
// Seconds to one decimal, rounded in whole tenths so 1450 ms reads 1.5 s (toFixed would give 1.4 because of floating point).
const secs = (ms: number) => `${(Math.round(ms / 100) / 10).toFixed(1)} s`
const date = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

function Score({ result }: { result: EvalResult }) {
  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium text-ink">{result.name}</span>
        <span className="shrink-0 font-semibold text-brand-strong">{result.percent}%</span>
      </div>
      <div
        role="progressbar" aria-label={result.name} aria-valuemin={0} aria-valuemax={100} aria-valuenow={result.percent}
        aria-valuetext={`${result.percent}% ${result.metric}, pass line ${result.pass_line_percent}%`}
        className="relative h-2.5 rounded-full bg-surface-2"
      >
        <div className="h-full rounded-full bg-brand" style={{ width: `${result.percent}%` }} />
        <div className="absolute top-[-2px] h-[14px] w-0.5 bg-ink" style={{ left: `${result.pass_line_percent}%` }} aria-hidden="true" />
      </div>
      <span className="text-xs text-muted">{result.metric} on {result.cases} cases. Pass line {result.pass_line_percent}% (the mark on the bar). {result.decision}</span>
    </li>
  )
}

function UsageView({ usage }: { usage: Usage }) {
  const { totals } = usage
  if (totals.calls === 0) return <p className="text-sm text-muted">No AI calls in the last {usage.days} days. Ask the coach something in the chat and they will show up here.</p>
  const busiest = Math.max(...usage.per_day.map((d) => d.calls), 1)
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-2 gap-2 text-sm">
        {[
          ['AI calls', totals.calls.toLocaleString('en-US')],
          ['Estimated cost', money(totals.cost_usd)],
          ['Tokens', (totals.input_tokens + totals.output_tokens).toLocaleString('en-US')],
          ['Average time', secs(totals.avg_latency_ms)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl bg-surface-2 p-3">
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="text-lg font-bold text-ink">{value}</dd>
          </div>
        ))}
      </dl>
      {totals.failed_calls > 0 && <p className="text-xs text-muted">{totals.failed_calls} of {totals.calls} calls were retried or failed (for example the model was busy).</p>}
      <ul aria-label="Calls per step" className="flex flex-col gap-1 text-sm text-ink-soft">
        {usage.per_step.map((s) => (
          <li key={s.step} className="flex justify-between gap-2">
            <span className="capitalize">{s.step}</span>
            <span className="text-muted">{s.calls} calls, {secs(s.avg_latency_ms)} each, {money(s.cost_usd)}</span>
          </li>
        ))}
      </ul>
      <ul aria-label="Calls per day" className="flex flex-col gap-1">
        {usage.per_day.map((d) => (
          <li key={d.day} className="flex items-center gap-2 text-xs text-muted">
            <span className="w-12 shrink-0">{date(d.day)}</span>
            <span className="h-2 rounded-full bg-brand" style={{ width: `${(d.calls / busiest) * 100}%`, minWidth: '4px' }} aria-hidden="true" />
            <span>{d.calls}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// "How the AI works": the rules it cannot break, how its quality is checked, and your own AI usage. A window into the engineering.
export function InsightsPage() {
  const api = useApi()
  const [data, setData] = useState<Insights | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    let cancelled = false
    api.get<Insights>('/insights/ai').then(
      (d) => { if (!cancelled) setData(d) },
      (e: unknown) => { if (!cancelled) setError(e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.')) },
    )
    return () => { cancelled = true }
  }, [api])

  return (
    <PageShell title="How the AI works" back>
      {error && <FormError message={error.message} requestId={error.requestId} />}
      {!data && !error && <p className="text-center text-sm text-muted">Loading…</p>}
      {data && (
        <>
          <section aria-label="Rules the AI cannot break" className="flex flex-col gap-2 rounded-2xl bg-surface p-4 shadow-sm">
            <h2 className="text-base font-bold text-ink">Rules the AI cannot break</h2>
            <p className="text-xs text-muted">Each of these is enforced by code and tested. None depends on the AI behaving well.</p>
            <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm text-ink-soft">{data.rules.map((r) => <li key={r}>{r}</li>)}</ul>
          </section>

          <section aria-label="How quality is checked" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm">
            <h2 className="text-base font-bold text-ink">How we check its quality</h2>
            <p className="text-xs text-muted">{data.quality.source} Results as of {date(data.quality.as_of)}.</p>
            <ul className="flex flex-col gap-3">{data.quality.evals.map((e) => <Score key={e.name} result={e} />)}</ul>
          </section>

          <section aria-label="Your AI usage" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm">
            <h2 className="text-base font-bold text-ink">Your AI usage, last {data.usage.days} days</h2>
            <UsageView usage={data.usage} />
            <p className="text-xs text-muted">Costs are estimates worked out in code from the tokens used. Every AI call is logged this way.</p>
          </section>
        </>
      )}
    </PageShell>
  )
}
