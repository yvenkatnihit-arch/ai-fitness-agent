import { useState, type FormEvent } from 'react'

import { Card, Choice, FieldError, FormError, Legend, PrimaryButton, inputClass } from '../components/ui'
import { GOALS, PACES } from './options'
import type { StepProps } from './types'
import { useSaveStep } from './useSaveStep'

export function GoalStep({ onSaved }: StepProps) {
  const { save, busy, error, fieldError } = useSaveStep('/onboarding/goal', onSaved)
  const [goal, setGoal] = useState('')
  const [target, setTarget] = useState('')
  const [pace, setPace] = useState('normal')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save({ goal_type: goal, target_weight_kg: target ? Number(target) : null, pace })
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

        <label className="flex flex-col gap-1 text-sm font-medium text-ink-soft">
          Target weight in kg (optional)
          <input type="number" inputMode="decimal" step="0.1" className={inputClass} value={target}
                 onChange={(e) => setTarget(e.target.value)} />
          <FieldError message={fieldError('target_weight_kg')} />
        </label>

        <fieldset className="flex flex-col gap-2">
          <Legend>How fast do you want to go?</Legend>
          {PACES.map(([value, label, hint]) => (
            <Choice key={value} type="radio" name="pace" checked={pace === value}
                    onChange={() => setPace(value)} label={label} hint={hint} />
          ))}
          <p className="text-xs text-muted">Whatever you pick, we never go past safe limits for calories or weight change.</p>
          <FieldError message={fieldError('pace')} />
        </fieldset>

        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton type="submit" disabled={!goal} busy={busy}>Continue</PrimaryButton>
      </form>
    </Card>
  )
}
