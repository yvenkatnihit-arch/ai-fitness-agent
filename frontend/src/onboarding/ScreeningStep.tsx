import { useState, type FormEvent } from 'react'

import { Card, Choice, FieldError, FormError, Legend, PrimaryButton } from '../components/ui'
import { INJURY_AREAS, SCREENING_QUESTIONS } from './options'
import type { StepProps } from './types'
import { useSaveStep } from './useSaveStep'

type Answers = Partial<Record<(typeof SCREENING_QUESTIONS)[number][0], boolean>>

export function ScreeningStep({ onSaved }: StepProps) {
  const { save, busy, error, fieldError } = useSaveStep('/onboarding/screening', onSaved)
  const [answers, setAnswers] = useState<Answers>({}) // no defaults: every question needs a real answer
  const [injuries, setInjuries] = useState<string[]>([])

  const allAnswered = SCREENING_QUESTIONS.every(([key]) => answers[key] !== undefined)
  const toggle = (area: string) =>
    setInjuries(injuries.includes(area) ? injuries.filter((a) => a !== area) : [...injuries, area])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save({ ...answers, injury_areas: injuries })
  }

  return (
    <Card title="Health check" subtitle="Your answers only make your plan more careful.">
      <form className="flex flex-col gap-5" onSubmit={handleSubmit} noValidate>
        {SCREENING_QUESTIONS.map(([key, question]) => (
          <fieldset key={key}>
            <Legend>{question}</Legend>
            <div className="grid grid-cols-2 gap-2">
              <Choice type="radio" name={key} checked={answers[key] === true}
                      onChange={() => setAnswers({ ...answers, [key]: true })} label="Yes" />
              <Choice type="radio" name={key} checked={answers[key] === false}
                      onChange={() => setAnswers({ ...answers, [key]: false })} label="No" />
            </div>
            <FieldError message={fieldError(key)} />
          </fieldset>
        ))}

        <fieldset>
          <Legend>Any areas to go easy on? (optional)</Legend>
          <div className="grid grid-cols-2 gap-2">
            {INJURY_AREAS.map(([value, label]) => (
              <Choice key={value} type="checkbox" name="injury_areas" checked={injuries.includes(value)}
                      onChange={() => toggle(value)} label={label} />
            ))}
          </div>
          <p className="mt-2 text-xs text-muted">
            Sharp pain, swelling or numbness? Please see a doctor or physiotherapist before training that area.
          </p>
        </fieldset>

        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton type="submit" disabled={!allAnswered} busy={busy}>Continue</PrimaryButton>
      </form>
    </Card>
  )
}
