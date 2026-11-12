import { Link } from 'react-router'

import { nextPlannedMeal, slotLabel } from './mealSlots'
import type { Today } from './types'

// "Next up" from today's meal plan: the first planned meal that is not logged yet and has not passed.
export function NextMealCard({ today, now }: { today: Today; now?: Date }) {
  if (!today.meal_plan) return null          // the Plan pane explains how to make a meal plan
  const next = nextPlannedMeal(today, now)
  return (
    <section aria-label="Next meal" className="glass flex flex-col gap-1 rounded-2xl p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Next up</h2>
      {next ? (
        <>
          <p className="text-base font-bold text-ink">{slotLabel(next.slot)}</p>
          <p className="text-sm text-ink-soft">{next.items.map((item) => `${item.name} (${item.text})`).join(', ')}</p>
          <Link to="/log" className="mt-1 text-sm font-semibold text-brand-strong">Log it when you eat</Link>
        </>
      ) : (
        <p className="text-sm text-ink-soft">No more planned meals for today. Anything else you eat can still be logged.</p>
      )}
    </section>
  )
}
