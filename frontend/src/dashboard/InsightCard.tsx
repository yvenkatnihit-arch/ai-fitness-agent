import { insightFor } from './insight'
import type { Today } from './types'

export function InsightCard({ today }: { today: Today }) {
  const text = insightFor(today)
  if (!text) return null
  return (
    <section aria-label="Today's insight" className="glass flex items-start gap-3 rounded-2xl p-4">
      <span aria-hidden="true" className="ring-glow mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-brand" />
      <p className="text-sm text-ink-soft">{text}</p>
    </section>
  )
}
