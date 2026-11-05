import { useState, type FormEvent } from 'react'

import { Card, Choice, FieldError, FormError, Legend, PrimaryButton, inputClass } from '../components/ui'
import { GOALS } from './options'
import type { StepProps } from './types'
import { useSaveStep } from './useSaveStep'

export function GoalStep({ onSaved }: StepProps) {
  const { save, busy, error, fieldError } = useSaveStep('/onboarding/goal', onSaved)
  const [goal, setGoal] = useState('')
  const [target, setTarget] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save({ goal_type: goal, target_weight_kg: target ? Number(target) : null })
  }

  return (
    <Card title="Your goal" subtitle="You can change this later.">
      <form className="flex flex-col gap-5" onSubmit={handleSubmit} noValidate>
        <fieldset className="flex flex-col gap-2">
          <Legend>What do you want to focus on?</Legend>
          {GOALS.map(([value, label, hint]) => (
            <Choice key={value} type="radio" name="goal" checked={goal === value}
                    onChange={() => setGoal(value)} label={label} hint={hint} />
          ))}
          <FieldError message={fieldError('goal_type')} />
        </fieldset>

        <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          Target weight in kg (optional)
          <input type="number" inputMode="decimal" step="0.1" className={inputClass} value={target}
                 onChange={(e) => setTarget(e.target.value)} />
          <FieldError message={fieldError('target_weight_kg')} />
        </label>

        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton type="submit" disabled={!goal} busy={busy}>Continue</PrimaryButton>
      </form>
    </Card>
  )
}
