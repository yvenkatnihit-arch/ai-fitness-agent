import { useState, type FormEvent } from 'react'

import { Card, FieldError, FormError, PrimaryButton, inputClass } from '../components/ui'
import { ACTIVITY_LEVELS, SEXES } from './options'
import type { StepProps } from './types'
import { useSaveStep } from './useSaveStep'

export function BasicsStep({ onSaved }: StepProps) {
  const { save, busy, error, fieldError } = useSaveStep('/onboarding/basics', onSaved)
  const [form, setForm] = useState({
    display_name: '',
    date_of_birth: '',
    sex: '',
    height_cm: '',
    weight_kg: '',
    activity_level: '',
  })
  const set = (field: keyof typeof form) => (value: string) => setForm({ ...form, [field]: value })
  const complete = form.date_of_birth && form.sex && form.height_cm && form.weight_kg && form.activity_level

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save({
      display_name: form.display_name.trim() || null,
      date_of_birth: form.date_of_birth,
      sex: form.sex,
      height_cm: Number(form.height_cm),
      weight_kg: Number(form.weight_kg),
      activity_level: form.activity_level,
    })
  }

  const labelClass = 'flex flex-col gap-1 text-sm font-medium text-slate-700'

  return (
    <Card title="About you" subtitle="We use this to calculate your daily targets.">
      <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
        <label className={labelClass}>
          Name (optional)
          <input className={inputClass} value={form.display_name} maxLength={80}
                 onChange={(e) => set('display_name')(e.target.value)} autoComplete="given-name" />
          <FieldError message={fieldError('display_name')} />
        </label>

        <label className={labelClass}>
          Date of birth
          <input type="date" className={inputClass} value={form.date_of_birth}
                 onChange={(e) => set('date_of_birth')(e.target.value)} autoComplete="bday" />
          <FieldError message={fieldError('date_of_birth')} />
        </label>

        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium text-slate-700">Sex (used only for the calorie formula)</legend>
          <div className="flex flex-wrap gap-2">
            {SEXES.map(([value, label]) => (
              <label key={value} className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <input type="radio" name="sex" value={value} checked={form.sex === value}
                       onChange={() => set('sex')(value)} className="accent-emerald-600" />
                {label}
              </label>
            ))}
          </div>
          <FieldError message={fieldError('sex')} />
        </fieldset>

        <div className="grid grid-cols-2 gap-3">
          <label className={labelClass}>
            Height (cm)
            <input type="number" inputMode="decimal" step="0.5" className={inputClass} value={form.height_cm}
                   onChange={(e) => set('height_cm')(e.target.value)} />
            <FieldError message={fieldError('height_cm')} />
          </label>
          <label className={labelClass}>
            Weight (kg)
            <input type="number" inputMode="decimal" step="0.1" className={inputClass} value={form.weight_kg}
                   onChange={(e) => set('weight_kg')(e.target.value)} />
            <FieldError message={fieldError('weight_kg')} />
          </label>
        </div>

        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium text-slate-700">How active are you?</legend>
          {ACTIVITY_LEVELS.map(([value, label, hint]) => (
            <label key={value} className="flex items-start gap-3 rounded-lg border border-slate-300 px-3 py-2">
              <input type="radio" name="activity_level" value={value} checked={form.activity_level === value}
                     onChange={() => set('activity_level')(value)} className="mt-1 accent-emerald-600" />
              <span className="text-sm">
                <span className="font-medium text-slate-800">{label}</span>
                <span className="block text-xs text-slate-500">{hint}</span>
              </span>
            </label>
          ))}
          <FieldError message={fieldError('activity_level')} />
        </fieldset>

        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton type="submit" disabled={!complete} busy={busy}>
          Continue
        </PrimaryButton>
      </form>
    </Card>
  )
}
