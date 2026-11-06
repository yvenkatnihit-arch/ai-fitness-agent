import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router'

import { useAuth } from '../auth/context'
import { FormError } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import type { OnboardingStatus } from '../onboarding/types'
import { TargetsView } from '../targets/TargetsView'
import type { Targets } from '../targets/types'

// Home: unfinished users go to onboarding; finished users see their daily targets.
// The full dashboard (today's progress, workout, logs) replaces this in Phase 9.
export function HomePage() {
  const { session, signOut } = useAuth()
  const api = useApi()
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [targets, setTargets] = useState<Targets | null>(null)
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
    <main className="flex min-h-screen flex-col items-center bg-slate-50 px-4 py-8">
      <div className="flex w-full max-w-md flex-col gap-4">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">AI Fitness Coach</h1>
            <p className="text-xs text-slate-500">{session?.user.email}</p>
          </div>
          <button
            type="button"
            onClick={() => signOut()}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700"
          >
            Sign out
          </button>
        </header>

        {error && <FormError message={error.message} requestId={error.requestId} />}
        {!error && !targets && <p className="text-center text-sm text-slate-500">Loading…</p>}
        {targets && (
          <Link to="/log" className="rounded-lg bg-emerald-600 px-4 py-2.5 text-center font-semibold text-white">
            Log a meal
          </Link>
        )}
        {targets && (
          <Link to="/exercises" className="rounded-lg border border-emerald-600 px-4 py-2.5 text-center font-semibold text-emerald-700">
            Exercise library
          </Link>
        )}
        {targets && <TargetsView targets={targets} />}
        <Link to="/sources" className="text-center text-xs text-slate-500 underline">Data sources</Link>
      </div>
    </main>
  )
}
