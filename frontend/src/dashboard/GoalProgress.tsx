import type { WeightHistory } from '../weight/types'

// How far along you are toward the target weight. Every number comes from the server (the weight history); nothing for users who must not see
// weights, and nothing until there is a target and at least one weigh-in.
export function GoalProgress({ history }: { history: WeightHistory | null }) {
  if (!history || history.numbers_hidden || history.percent_to_target === null || history.target_weight_kg === null || history.latest_kg === null) return null
  const percent = Math.max(0, Math.min(100, Math.round(history.percent_to_target)))
  return (
    <section aria-label="Goal progress" className="glass flex flex-col gap-2 rounded-2xl p-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-bold text-ink">Goal progress</h2>
        <span className="text-sm font-semibold text-brand-strong">{percent}%</span>
      </div>
      <div
        role="progressbar" aria-label="Goal progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
        aria-valuetext={`${percent}% of the way to your target weight`} className="h-2 overflow-hidden rounded-full bg-surface-2"
      >
        <div className="h-full rounded-full bg-brand transition-[width] duration-1000 ease-out" style={{ width: `${percent}%` }} />
      </div>
      <p className="text-xs text-muted">
        {history.start_weight_kg !== null ? `Started at ${history.start_weight_kg} kg, ` : ''}now {history.latest_kg} kg, target {history.target_weight_kg} kg.
      </p>
    </section>
  )
}
