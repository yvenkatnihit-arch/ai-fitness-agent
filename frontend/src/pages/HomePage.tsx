import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router'

import { useAuth } from '../auth/context'
import { ButtonLink, FormError, PageShell } from '../components/ui'
import { ApiError } from '../lib/api'
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
          <ButtonLink to="/log">Log a meal</ButtonLink>
          <div className="grid grid-cols-2 gap-3">
            <ButtonLink to="/workout" variant="secondary">Workout plan</ButtonLink>
            <ButtonLink to="/splits" variant="secondary">Workout split</ButtonLink>
          </div>
        </div>
      )}
      {targets && <TargetsView targets={targets} />}
      {targets && forecast && <ForecastCard forecast={forecast} />}
      <Link to="/sources" className="text-center text-xs text-muted underline">Data sources</Link>
    </PageShell>
  )
}
