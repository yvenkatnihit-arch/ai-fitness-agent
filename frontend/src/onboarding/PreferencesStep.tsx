import { useState, type FormEvent } from 'react'

import { Card, Choice, FieldError, FormError, Legend, PrimaryButton, inputClass } from '../components/ui'
import { CUISINES, DIETS, MAX_DISLIKED_FOODS } from './options'
import type { StepProps } from './types'
import { useSaveStep } from './useSaveStep'

export function PreferencesStep({ onSaved }: StepProps) {
  const { save, busy, error, fieldError } = useSaveStep('/onboarding/preferences', onSaved)
  const [diet, setDiet] = useState('')
  const [cuisines, setCuisines] = useState<string[]>(['indian'])   // one or more; the server needs at least one
  const [foods, setFoods] = useState<string[]>([])
  const [draft, setDraft] = useState('')

  function addFood() {
    const food = draft.trim()
    const alreadyThere = foods.some((f) => f.toLowerCase() === food.toLowerCase())
    if (food && !alreadyThere && foods.length < MAX_DISLIKED_FOODS) setFoods([...foods, food])
    setDraft('')
  }

  function toggleCuisine(value: string) {
    setCuisines(cuisines.includes(value) ? cuisines.filter((c) => c !== value) : [...cuisines, value])
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save({ diet_type: diet, cuisines, disliked_foods: foods })
  }

  return (
    <Card title="Food preferences" subtitle="Your meal plans will only use foods that fit.">
      <form className="flex flex-col gap-5" onSubmit={handleSubmit} noValidate>
        <fieldset className="flex flex-col gap-2">
          <Legend>Which cuisines should your meals come from? (pick one or more)</Legend>
          {CUISINES.map(([value, label, hint]) => (
            <Choice key={value} type="checkbox" name="cuisines" checked={cuisines.includes(value)}
                    onChange={() => toggleCuisine(value)} label={label} hint={hint} />
          ))}
          <p className="text-xs text-muted">More cuisines are coming. We add each one only after its food data is checked. You can change this later in Settings.</p>
          <FieldError message={fieldError('cuisines')} />
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <Legend>How do you eat?</Legend>
          {DIETS.map(([value, label, hint]) => (
            <Choice key={value} type="radio" name="diet" checked={diet === value}
                    onChange={() => setDiet(value)} label={label} hint={hint} />
          ))}
          <FieldError message={fieldError('diet_type')} />
        </fieldset>

        <div className="flex flex-col gap-2">
          <label htmlFor="disliked-food" className="text-sm font-medium text-ink-soft">
            Foods you don't like (optional)
          </label>
          <div className="flex gap-2">
            <input
              id="disliked-food"
              className={`${inputClass} min-w-0 flex-1`}
              value={draft}
              maxLength={60}
              placeholder="e.g. karela"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault() // Enter adds the food instead of submitting the form
                  addFood()
                }
              }}
            />
            <button type="button" onClick={addFood} disabled={!draft.trim() || foods.length >= MAX_DISLIKED_FOODS}
                    className="rounded-lg border border-line px-3 text-sm font-medium text-ink-soft disabled:opacity-50">
              Add
            </button>
          </div>
          {foods.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="Foods you don't like">
              {foods.map((food) => (
                <li key={food} className="flex items-center gap-1 rounded-full bg-surface-2 px-3 py-1 text-sm text-ink-soft">
                  {food}
                  <button type="button" aria-label={`Remove ${food}`} className="text-muted"
                          onClick={() => setFoods(foods.filter((f) => f !== food))}>
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <FieldError message={fieldError('disliked_foods')} />
        </div>

        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton type="submit" disabled={!diet || cuisines.length === 0} busy={busy}>Continue</PrimaryButton>
      </form>
    </Card>
  )
}
