import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router'

import { useAuth } from '../auth/context'
import { ButtonLink, FormError, PageShell } from '../components/ui'
import { TodayPlans } from '../dashboard/TodayPlans'
import { TodayProgress } from '../dashboard/TodayProgress'
import type { Today } from '../dashboard/types'
import { ApiError } from '../lib/api'
import { WeightCard } from '../weight/WeightCard'
import { useApi } from '../lib/useApi'
import type { OnboardingStatus } from '../onboarding/types'
import { TargetsView } from '../targets/TargetsView'
import { ForecastCard } from '../targets/ForecastCard'
import type { Forecast, Targets } from '../targets/types'

// Home: unfinished users go to onboarding; finished users see their daily targets.
// The full dashboard (today's progress, workout, logs) replaces this in Phase 9.
export function HomePage() {
  const { session, signOut } = useAuth()
  const api = useApi()
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [targets, setTargets] = useState<Targets | null>(null)
  const [forecast, setForecast] = useState<Forecast | null>(null)
  const [today, setToday] = useState<Today | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const current = await api.get<OnboardingStatus>('/onboarding/status')
        if (cancelled) return
        setStatus(current)
        if (current.completed) {
          const loaded = await api.get<Targets>('/targets/current')
          if (!cancelled) setTargets(loaded)
          // The goal date is a bonus: if it can't load, the rest of the page still works.
          const dated = await api.get<Forecast>('/targets/forecast').catch(() => null)
          if (!cancelled) setForecast(dated)
          // Today's summary is a bonus too: if it cannot load, the targets below still show.
          const summary = await api.get<Today>('/dashboard/today').catch(() => null)
          if (!cancelled) setToday(summary)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))
      }
    }
    load()
    return () => {
      cancelled = true // the page was left (or the token changed) before the answers came back
    }
  }, [api])

  // A weigh-in moves the goal date (it starts from the latest weight), so the forecast is asked for again.
  const refreshForecast = () => { api.get<Forecast>('/targets/forecast').then(setForecast, () => {}) }

  if (status && !status.completed) return <Navigate to="/onboarding" replace />

  return (
    <PageShell
      title="AI Fitness Coach"
      subtitle={session?.user.email}
      action={
        <button
          type="button"
          onClick={() => signOut()}
          className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-ink-soft transition hover:bg-surface-2"
        >
          Sign out
        </button>
      }
    >
      {error && <FormError message={error.message} requestId={error.requestId} />}
      {!error && !targets && <p className="text-center text-sm text-muted">Loading…</p>}
      {targets && (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <ButtonLink to="/log">Log a meal</ButtonLink>
            <ButtonLink to="/meal-plan">Meal plan</ButtonLink>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <ButtonLink to="/workout" variant="secondary">Workout plan</ButtonLink>
            <ButtonLink to="/splits" variant="secondary">Workout split</ButtonLink>
          </div>
          <ButtonLink to="/settings" variant="secondary">Settings</ButtonLink>
        </div>
      )}
      {today && <TodayProgress today={today} />}
      {today && <TodayPlans today={today} />}
      {targets && <WeightCard onChanged={refreshForecast} />}
      {targets && <TargetsView targets={targets} />}
      {targets && forecast && <ForecastCard forecast={forecast} />}
      <div className="flex justify-center gap-4 text-xs text-muted">
        <Link to="/how-it-works" className="underline">How the AI works</Link>
        <Link to="/sources" className="underline">Data sources</Link>
      </div>
    </PageShell>
  )
}
