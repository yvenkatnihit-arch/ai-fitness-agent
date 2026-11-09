import { useState } from 'react'

import { Choice, FieldError, Legend, inputClass } from '../components/ui'
import {
  ACTIVITY_LEVELS, DIETS, EQUIPMENT, EXPERIENCE, GOALS, INJURY_AREAS, LOCATIONS, PACES, SCREENING_QUESTIONS, SESSION_MINUTES, SEXES,
} from '../onboarding/options'
import { SectionCard } from './SectionCard'
import { changedFields, parseList, type Changes, type Profile } from './types'

type SectionProps = {
  profile: Profile
  saving: boolean
  error: import('../lib/api').ApiError | null
  onSave: (changes: Changes) => void
}

const labelClass = 'flex flex-col gap-1 text-sm font-medium text-ink-soft'
const num = (text: string) => (text.trim() === '' ? NaN : Number(text))

export function AboutSection({ profile, saving, error, onSave }: SectionProps) {
  const [name, setName] = useState(profile.display_name ?? '')
  const [dob, setDob] = useState(profile.date_of_birth)
  const [sex, setSex] = useState(profile.sex)
  const [height, setHeight] = useState(String(profile.height_cm))
  const [weight, setWeight] = useState(String(profile.weight_kg))
  const [activity, setActivity] = useState(profile.activity_level)
  const fe = (f: string) => error?.fieldErrors[f]
  const changes = changedFields(profile, {
    display_name: name.trim() || null, date_of_birth: dob, sex, height_cm: num(height), weight_kg: num(weight), activity_level: activity,
  })
  return (
    <SectionCard title="About you" hint="Changing your weight, height, age or activity updates your daily targets." changes={changes}
                 saving={saving} error={error} onSave={onSave}>
      <label className={labelClass}>Name (optional)
        <input className={inputClass} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        <FieldError message={fe('display_name')} />
      </label>
      <label className={labelClass}>Date of birth
        <input type="date" className={inputClass} value={dob} onChange={(e) => setDob(e.target.value)} />
        <FieldError message={fe('date_of_birth')} />
      </label>
      <fieldset>
        <Legend>Sex (used only for the calorie formula)</Legend>
        <div className="flex flex-wrap gap-2">
          {SEXES.map(([value, label]) => <Choice key={value} type="radio" name="sex" checked={sex === value} onChange={() => setSex(value)} label={label} />)}
        </div>
        <FieldError message={fe('sex')} />
      </fieldset>
      <label className={labelClass}>Height (cm)
        <input inputMode="decimal" className={inputClass} value={height} onChange={(e) => setHeight(e.target.value)} />
        <FieldError message={fe('height_cm')} />
      </label>
      <label className={labelClass}>Weight (kg)
        <input inputMode="decimal" className={inputClass} value={weight} onChange={(e) => setWeight(e.target.value)} />
        <FieldError message={fe('weight_kg')} />
      </label>
      <fieldset className="flex flex-col gap-2">
        <Legend>How active are you?</Legend>
        {ACTIVITY_LEVELS.map(([value, label, hint]) => (
          <Choice key={value} type="radio" name="activity" checked={activity === value} onChange={() => setActivity(value)} label={label} hint={hint} />
        ))}
        <FieldError message={fe('activity_level')} />
      </fieldset>
    </SectionCard>
  )
}

export function GoalSection({ profile, saving, error, onSave }: SectionProps) {
  const [goal, setGoal] = useState(profile.goal_type)
  const [target, setTarget] = useState(profile.target_weight_kg === null ? '' : String(profile.target_weight_kg))
  const [pace, setPace] = useState(profile.pace)
  const fe = (f: string) => error?.fieldErrors[f]
  const changes = changedFields(profile, { goal_type: goal, target_weight_kg: target.trim() === '' ? null : num(target), pace })
  return (
    <SectionCard title="Your goal" hint="Changing the goal type starts a new goal from today's weight; your old one is kept in your history."
                 changes={changes} saving={saving} error={error} onSave={onSave}>
      <fieldset className="flex flex-col gap-2">
        <Legend>What do you want?</Legend>
        {GOALS.map(([value, label, hint]) => <Choice key={value} type="radio" name="goal" checked={goal === value} onChange={() => setGoal(value)} label={label} hint={hint} />)}
        <FieldError message={fe('goal_type')} />
      </fieldset>
      <label className={labelClass}>Target weight (kg, optional)
        <input inputMode="decimal" className={inputClass} value={target} onChange={(e) => setTarget(e.target.value)} />
        <FieldError message={fe('target_weight_kg')} />
      </label>
      <fieldset className="flex flex-col gap-2">
        <Legend>How fast?</Legend>
        {PACES.map(([value, label, hint]) => <Choice key={value} type="radio" name="pace" checked={pace === value} onChange={() => setPace(value)} label={label} hint={hint} />)}
        <FieldError message={fe('pace')} />
      </fieldset>
    </SectionCard>
  )
}

export function FoodSection({ profile, saving, error, onSave }: SectionProps) {
  const [diet, setDiet] = useState(profile.diet_type)
  const [dislikes, setDislikes] = useState(profile.disliked_foods.join(', '))
  const fe = (f: string) => error?.fieldErrors[f]
  const changes = changedFields(profile, { diet_type: diet, disliked_foods: parseList(dislikes) })
  return (
    <SectionCard title="Food" hint="A new diet or dislikes means your meal plan needs to be made again." changes={changes}
                 saving={saving} error={error} onSave={onSave}>
      <fieldset className="flex flex-col gap-2">
        <Legend>Diet</Legend>
        {DIETS.map(([value, label, hint]) => <Choice key={value} type="radio" name="diet" checked={diet === value} onChange={() => setDiet(value)} label={label} hint={hint} />)}
        <FieldError message={fe('diet_type')} />
      </fieldset>
      <label className={labelClass}>Foods you dislike (separate with commas)
        <input className={inputClass} value={dislikes} onChange={(e) => setDislikes(e.target.value)} />
        <FieldError message={fe('disliked_foods') ?? Object.entries(error?.fieldErrors ?? {}).find(([k]) => k.startsWith('disliked_foods.'))?.[1]} />
      </label>
    </SectionCard>
  )
}

export function TrainingSection({ profile, saving, error, onSave }: SectionProps) {
  const [level, setLevel] = useState(profile.experience_level)
  const [place, setPlace] = useState(profile.workout_location)
  const [equipment, setEquipment] = useState(profile.equipment)
  const [days, setDays] = useState(profile.days_per_week)
  const [minutes, setMinutes] = useState(profile.session_minutes ?? 60)
  const fe = (f: string) => error?.fieldErrors[f]
  const changes = changedFields(profile, { experience_level: level, workout_location: place, equipment, days_per_week: days, session_minutes: minutes })
  const toggle = (item: string) => setEquipment(equipment.includes(item) ? equipment.filter((e) => e !== item) : [...equipment, item])
  return (
    <SectionCard title="Training" hint="Changing these means your workout plan needs to be made again." changes={changes}
                 saving={saving} error={error} onSave={onSave}>
      <fieldset className="flex flex-col gap-2">
        <Legend>Experience</Legend>
        {EXPERIENCE.map(([value, label, hint]) => <Choice key={value} type="radio" name="experience" checked={level === value} onChange={() => setLevel(value)} label={label} hint={hint} />)}
        <FieldError message={fe('experience_level')} />
      </fieldset>
      <fieldset>
        <Legend>Where do you train?</Legend>
        <div className="grid grid-cols-3 gap-2">
          {LOCATIONS.map(([value, label]) => <Choice key={value} type="radio" name="place" checked={place === value} onChange={() => setPlace(value)} label={label} />)}
        </div>
      </fieldset>
      <fieldset>
        <Legend>Equipment you can use</Legend>
        <div className="grid grid-cols-2 gap-2">
          {EQUIPMENT.map(([value, label]) => <Choice key={value} type="checkbox" name="equipment" checked={equipment.includes(value)} onChange={() => toggle(value)} label={label} />)}
        </div>
        <FieldError message={Object.entries(error?.fieldErrors ?? {}).find(([k]) => k.startsWith('equipment'))?.[1]} />
      </fieldset>
      <fieldset>
        <Legend>Days per week</Legend>
        <div className="flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5, 6, 7].map((n) => (
            <button key={n} type="button" aria-pressed={days === n} onClick={() => setDays(n)}
                    className={`h-10 w-10 rounded-full border text-sm font-medium ${days === n ? 'border-brand bg-brand text-on-brand' : 'border-line text-ink-soft'}`}>
              {n}
            </button>
          ))}
        </div>
        <FieldError message={fe('days_per_week')} />
      </fieldset>
      <fieldset>
        <Legend>How long can a workout last?</Legend>
        <div className="grid grid-cols-2 gap-2">
          {SESSION_MINUTES.map(([value, label, hint]) => <Choice key={value} type="radio" name="minutes" checked={minutes === value} onChange={() => setMinutes(value)} label={label} hint={hint} />)}
        </div>
        <FieldError message={fe('session_minutes')} />
      </fieldset>
    </SectionCard>
  )
}

export function HealthSection({ profile, saving, error, onSave }: SectionProps) {
  const [flags, setFlags] = useState(() => Object.fromEntries(SCREENING_QUESTIONS.map(([key]) => [key, profile[key]])) as Record<string, boolean>)
  const [injuries, setInjuries] = useState(profile.injury_areas)
  const changes = changedFields(profile, { ...flags, injury_areas: injuries } as Partial<Profile>)
  const toggle = (area: string) => setInjuries(injuries.includes(area) ? injuries.filter((a) => a !== area) : [...injuries, area])
  return (
    <SectionCard title="Health" hint="Your answers only make your plans more careful. A change here updates your targets and both plans."
                 changes={changes} saving={saving} error={error} onSave={onSave}>
      {SCREENING_QUESTIONS.map(([key, question]) => (
        <fieldset key={key}>
          <Legend>{question}</Legend>
          <div className="grid grid-cols-2 gap-2">
            <Choice type="radio" name={key} checked={flags[key] === true} onChange={() => setFlags({ ...flags, [key]: true })} label="Yes" />
            <Choice type="radio" name={key} checked={flags[key] === false} onChange={() => setFlags({ ...flags, [key]: false })} label="No" />
          </div>
          <FieldError message={error?.fieldErrors[key]} />
        </fieldset>
      ))}
      <fieldset>
        <Legend>Any areas to go easy on?</Legend>
        <div className="grid grid-cols-2 gap-2">
          {INJURY_AREAS.map(([value, label]) => <Choice key={value} type="checkbox" name="injury_areas" checked={injuries.includes(value)} onChange={() => toggle(value)} label={label} />)}
        </div>
        <p className="mt-2 text-xs text-muted">Sharp pain, swelling or numbness? Please see a doctor or physiotherapist before training that area.</p>
      </fieldset>
    </SectionCard>
  )
}
