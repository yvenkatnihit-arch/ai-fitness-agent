import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { ButtonLink, FormError, PageShell } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { AboutSection, FoodSection, GoalSection, HealthSection, TrainingSection } from './Sections'
import type { Changes, Profile, ProfileUpdate } from './types'

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))

type SectionName = 'about' | 'goal' | 'food' | 'training' | 'health'

// Settings: change your answers. Only what you changed is sent; the server checks it exactly like onboarding, recalculates your
// targets when needed, and tells us which plans no longer match (we only suggest making a new one: nothing is rewritten).
export function SettingsPage() {
  const api = useApi()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loadError, setLoadError] = useState<ApiError | null>(null)
  const [saving, setSaving] = useState<SectionName | null>(null)
  const [errorSection, setErrorSection] = useState<{ section: SectionName; error: ApiError } | null>(null)
  const [result, setResult] = useState<ProfileUpdate | null>(null)

  useEffect(() => {
    let cancelled = false
    api.get<Profile>('/profile').then(
      (loaded) => { if (!cancelled) setProfile(loaded) },
      (e: unknown) => { if (!cancelled) setLoadError(asApiError(e)) },
    )
    return () => {
      cancelled = true
    }
  }, [api])

  async function save(section: SectionName, changes: Changes) {
    setSaving(section)
    setErrorSection(null)
    try {
      const update = await api.patch<ProfileUpdate>('/profile', changes)
      setProfile(update.profile)
      setResult(update)
    } catch (e) {
      setErrorSection({ section, error: asApiError(e) })
    } finally {
      setSaving(null)
    }
  }

  const props = (section: SectionName) => ({
    saving: saving === section,
    error: errorSection?.section === section ? errorSection.error : null,
    onSave: (changes: Changes) => save(section, changes),
  })

  return (
    <PageShell title="Settings" back>
      {loadError && (
        <>
          <FormError message={loadError.message} requestId={loadError.requestId} />
          {loadError.status === 409 && <Link to="/onboarding" className="text-sm font-semibold text-brand-strong">Go to onboarding</Link>}
        </>
      )}
      {!profile && !loadError && <p className="text-center text-sm text-muted">Loading…</p>}

      {result && result.messages.length > 0 && (
        <section aria-label="What changed" className="flex flex-col gap-3 rounded-2xl bg-brand-soft p-4">
          <h2 className="text-sm font-bold text-ink">Saved</h2>
          <ul className="flex flex-col gap-1 text-sm text-ink-soft">
            {result.messages.map((message) => <li key={message}>{message}</li>)}
          </ul>
          {result.targets && !result.targets.focus_on_habits && result.targets.calorie_target_kcal !== null && (
            <p className="text-sm font-semibold text-ink">
              New daily target: {result.targets.calorie_target_kcal} kcal · protein {result.targets.protein_g} g · carbs {result.targets.carbs_g} g · fat {result.targets.fat_g} g
            </p>
          )}
          {result.targets?.doctor_note && <p className="rounded-lg bg-warn-soft p-2 text-xs text-warn">{result.targets.doctor_note}</p>}
          {(result.meal_plan_stale || result.workout_plan_stale) && (
            <div className="grid grid-cols-2 gap-3">
              {result.meal_plan_stale && <ButtonLink to="/meal-plan">New meal plan</ButtonLink>}
              {result.workout_plan_stale && <ButtonLink to="/workout">New workout plan</ButtonLink>}
            </div>
          )}
        </section>
      )}
      {result && result.changed.length === 0 && <p role="status" className="text-sm text-muted">Nothing needed changing.</p>}

      {profile && (
        <div className="flex flex-col gap-3">
          <AboutSection profile={profile} {...props('about')} />
          <GoalSection profile={profile} {...props('goal')} />
          <FoodSection profile={profile} {...props('food')} />
          <TrainingSection profile={profile} {...props('training')} />
          <HealthSection profile={profile} {...props('health')} />
        </div>
      )}
    </PageShell>
  )
}
