import { SLOTS, type Day, type Nutrition } from './types'

const slotLabel = (slot: string) => SLOTS.find((s) => s.value === slot)?.label ?? slot

// Numbers come from the backend; the screen only rounds them for display.
export function NutritionLine({ n }: { n: Nutrition }) {
  return (
    <span className="text-xs text-muted">
      {Math.round(n.kcal)} kcal · P {Math.round(n.protein_g)} g · C {Math.round(n.carbs_g)} g · F {Math.round(n.fat_g)} g
    </span>
  )
}

export function TodayMeals({ day, onDelete, deleting }: {
  day: Day
  onDelete: (mealId: string) => void
  deleting: string | null
}) {
  return (
    <section aria-label="Today's meals" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-semibold text-ink">Today</h2>
        <span aria-label="Day total" className="text-sm font-semibold text-ink">{Math.round(day.totals.kcal)} kcal</span>
      </div>
      {day.meals.length === 0 && <p className="text-sm text-muted">Nothing logged yet today.</p>}
      {day.meals.map((meal) => (
        <article key={meal.id} className="rounded-xl bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">{slotLabel(meal.slot)}</h3>
            <button
              type="button"
              onClick={() => onDelete(meal.id)}
              disabled={deleting === meal.id}
              aria-label={`Delete ${slotLabel(meal.slot)}`}
              className="text-xs text-danger disabled:opacity-50"
            >
              {deleting === meal.id ? 'Deleting…' : 'Delete'}
            </button>
          </div>
          <ul className="mt-2 flex flex-col gap-1">
            {meal.items.map((item) => (
              <li key={item.id} className="flex justify-between gap-2 text-sm text-ink-soft">
                <span>{item.quantity} {item.unit === 'g' ? 'g' : item.unit} {item.food_name}</span>
                <span className="shrink-0 text-muted">{Math.round(item.kcal)} kcal</span>
              </li>
            ))}
          </ul>
          <div className="mt-2"><NutritionLine n={meal.totals} /></div>
        </article>
      ))}
      {day.meals.length > 0 && (
        <p className="text-right"><NutritionLine n={day.totals} /></p>
      )}
    </section>
  )
}
