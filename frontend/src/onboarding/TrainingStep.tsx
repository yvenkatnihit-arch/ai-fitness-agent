import { useState, type FormEvent } from 'react'

import { Card, Choice, FieldError, FormError, Legend, PrimaryButton } from '../components/ui'
import { EQUIPMENT, EXPERIENCE, LOCATIONS, SESSION_MINUTES } from './options'
import type { StepProps } from './types'
import { useSaveStep } from './useSaveStep'

const DAYS = [1, 2, 3, 4, 5, 6, 7]

export function TrainingStep({ onSaved }: StepProps) {
  const { save, busy, error, fieldError } = useSaveStep('/onboarding/training', onSaved)
  const [experience, setExperience] = useState('')
  const [location, setLocation] = useState('')
  const [equipment, setEquipment] = useState<string[]>([])
  const [days, setDays] = useState<number | null>(null)
  const [minutes, setMinutes] = useState<number | null>(null)

  const toggle = (item: string) =>
    setEquipment(equipment.includes(item) ? equipment.filter((e) => e !== item) : [...equipment, item])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save({ experience_level: experience, workout_location: location, equipment, days_per_week: days, session_minutes: minutes })
  }

  return (
    <Card title="Your training" subtitle="So your workouts fit your space, equipment and week.">
      <form className="flex flex-col gap-5" onSubmit={handleSubmit} noValidate>
        <fieldset className="flex flex-col gap-2">
          <Legend>Experience</Legend>
          {EXPERIENCE.map(([value, label, hint]) => (
            <Choice key={value} type="radio" name="experience" checked={experience === value}
                    onChange={() => setExperience(value)} label={label} hint={hint} />
          ))}
          <FieldError message={fieldError('experience_level')} />
        </fieldset>

        <fieldset>
          <Legend>Where do you train?</Legend>
          <div className="grid grid-cols-3 gap-2">
            {LOCATIONS.map(([value, label]) => (
              <Choice key={value} type="radio" name="location" checked={location === value}
                      onChange={() => setLocation(value)} label={label} />
            ))}
          </div>
          <FieldError message={fieldError('workout_location')} />
        </fieldset>

        <fieldset>
          <Legend>Equipment you can use (tick all that apply; none is fine)</Legend>
          <div className="grid grid-cols-2 gap-2">
            {EQUIPMENT.map(([value, label]) => (
              <Choice key={value} type="checkbox" name="equipment" checked={equipment.includes(value)}
                      onChange={() => toggle(value)} label={label} />
            ))}
          </div>
          <FieldError message={fieldError('equipment')} />
        </fieldset>

        <fieldset>
          <Legend>Days per week you can train</Legend>
          <div className="flex flex-wrap gap-2">
            {DAYS.map((n) => (
              <button key={n} type="button" aria-pressed={days === n} onClick={() => setDays(n)}
                      className={`h-10 w-10 rounded-full border text-sm font-medium ${days === n ? 'border-brand bg-brand text-on-brand' : 'border-line text-ink-soft'}`}>
                {n}
              </button>
            ))}
          </div>
          <FieldError message={fieldError('days_per_week')} />
        </fieldset>

        <fieldset>
          <Legend>How long can a workout last?</Legend>
          <div className="grid grid-cols-2 gap-2">
            {SESSION_MINUTES.map(([value, label, hint]) => (
              <Choice key={value} type="radio" name="session_minutes" checked={minutes === value}
                      onChange={() => setMinutes(value)} label={label} hint={hint} />
            ))}
          </div>
          <FieldError message={fieldError('session_minutes')} />
        </fieldset>

        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton type="submit" disabled={!experience || !location || !days || !minutes} busy={busy}>Continue</PrimaryButton>
      </form>
    </Card>
  )
}
