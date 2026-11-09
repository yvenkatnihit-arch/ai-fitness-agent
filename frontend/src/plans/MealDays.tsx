import { WEEKDAYS } from './types'
import { SLOT_LABEL, type MealDayView, type Totals } from './mealTypes'

const kcal = (n: number | null | undefined) => (typeof n === 'number' ? `${Math.round(n)} kcal` : null)

function dayLine(totals: Totals | null | undefined, target: Totals | null | undefined) {
  if (!totals) return null
  const base = `${Math.round(totals.kcal)} kcal · P ${Math.round(totals.protein_g)} · C ${Math.round(totals.carbs_g)} · F ${Math.round(totals.fat_g)}`
  return target ? `${base} (target ${Math.round(target.kcal)} kcal)` : base
}

// The week, day by day, meal by meal. Calories and macros appear only when the server sent them.
export function MealDays({ days, targets }: { days: MealDayView[]; targets?: Totals | null }) {
  return (
    <ol aria-label="Week of meals" className="flex flex-col gap-2">
      {days.map((day, index) => (
        <li key={day.day_of_week}>
          <details open={index === 0} className="rounded-xl bg-surface-2 p-3">
            <summary className="cursor-pointer text-sm font-bold text-ink">
              {WEEKDAYS[day.day_of_week - 1]}
              {dayLine(day.totals, targets) && <span className="ml-2 text-xs font-normal text-muted">{dayLine(day.totals, targets)}</span>}
            </summary>
            <div className="mt-2 flex flex-col gap-3">
              {day.meals.map((meal) => (
                <section key={meal.slot} aria-label={`${WEEKDAYS[day.day_of_week - 1]} ${SLOT_LABEL[meal.slot] ?? meal.slot}`}>
                  <h4 className="text-xs font-bold uppercase tracking-wide text-muted">{SLOT_LABEL[meal.slot] ?? meal.slot}</h4>
                  <ul className="mt-1 flex flex-col gap-1">
                    {meal.items.map((item) => (
                      <li key={item.position} className="flex items-baseline justify-between gap-3 text-sm">
                        <span className="text-ink">
                          {item.name} <span className="text-xs text-ink-soft">{item.text}</span>
                        </span>
                        {kcal(item.kcal) && <span className="shrink-0 text-xs text-muted">{kcal(item.kcal)}</span>}
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </details>
        </li>
      ))}
    </ol>
  )
}
