import { useCallback, useEffect, useState } from 'react'
import { FormError, PageShell, PrimaryButton, inputClass } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { AmountPicker } from './AmountPicker'
import { FoodSearch } from './FoodSearch'
import { defaultSlot } from './slots'
import { TodayMeals } from './TodayMeals'
import { SLOTS, type Day, type DraftItem, type FoodHit, type Meal, type Slot } from './types'

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))

// Log a meal from a form: pick foods and amounts; the backend computes grams and nutrition (no LLM).
export function MealLogPage() {
  const api = useApi()
  const [slot, setSlot] = useState<Slot>(() => defaultSlot())
  const [picked, setPicked] = useState<FoodHit | null>(null)
  const [draft, setDraft] = useState<DraftItem[]>([])
  const [day, setDay] = useState<Day | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  const loadDay = useCallback(async () => {
    try {
      setDay(await api.get<Day>('/meals'))
    } catch (e) {
      setError(asApiError(e))
    }
  }, [api])

  // First load. (After saving or deleting, loadDay() refreshes the day.)
  useEffect(() => {
    let cancelled = false
    api.get<Day>('/meals').then(
      (loaded) => { if (!cancelled) setDay(loaded) },
      (e: unknown) => { if (!cancelled) setError(asApiError(e)) },
    )
    return () => {
      cancelled = true // the page was left (or the token changed) before the answer came back
    }
  }, [api])

  async function save() {
    setSaving(true)
    setError(null)
    try {
      await api.post<Meal>('/meals', {
        slot,
        items: draft.map((d) => ({ food_id: d.food.id, quantity: d.quantity, unit: d.unit })),
      })
      setDraft([])
      await loadDay()
    } catch (e) {
      setError(asApiError(e)) // e.g. "Item 1 (Roti): this food can't be measured in 'katori'..."
    } finally {
      setSaving(false)
    }
  }

  async function remove(mealId: string) {
    setDeleting(mealId)
    setError(null)
    try {
      await api.delete(`/meals/${mealId}`)
      await loadDay()
    } catch (e) {
      setError(asApiError(e))
    } finally {
      setDeleting(null)
    }
  }

  return (
    <PageShell title="Log a meal" back>

        <section className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm">
          <label className="flex flex-col gap-1 text-sm font-medium text-ink-soft">
            Meal
            <select value={slot} onChange={(e) => setSlot(e.target.value as Slot)} className={inputClass}>
              {SLOTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </label>

          {picked ? (
            <AmountPicker
              food={picked}
              onAdd={(item) => {
                setDraft((items) => [...items, item])
                setPicked(null)
              }}
              onCancel={() => setPicked(null)}
            />
          ) : (
            <FoodSearch onPick={setPicked} />
          )}

          {draft.length > 0 && (
            <ul aria-label="This meal" className="flex flex-col gap-1">
              {draft.map((d, index) => (
                <li key={index} className="flex items-center justify-between gap-2 text-sm text-ink-soft">
                  <span>{d.quantity} {d.unit} {d.food.name}</span>
                  <button
                    type="button"
                    aria-label={`Remove ${d.food.name}`}
                    onClick={() => setDraft((items) => items.filter((_, i) => i !== index))}
                    className="text-xs text-muted"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}

          <FormError message={error?.message ?? null} requestId={error?.requestId} />
          <PrimaryButton type="button" busy={saving} disabled={draft.length === 0} onClick={save}>
            Save meal
          </PrimaryButton>
        </section>

        {day ? <TodayMeals day={day} onDelete={remove} deleting={deleting} /> : <p className="text-center text-sm text-muted">Loading…</p>}
    </PageShell>
  )
}
