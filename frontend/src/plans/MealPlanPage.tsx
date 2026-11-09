import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { FormError, PageShell, PrimaryButton } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { HowMadePanel } from './HowMadePanel'
import { MealDays } from './MealDays'
import { daysFromPayload, type ActiveMealPlan, type MealProposal } from './mealTypes'

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))

// Your meal plan. A plan the coach builds is only a PROPOSAL until you press Approve; then it becomes your plan.
// Building takes about a minute (the AI picks dishes, our code works out the portions and checks everything).
export function MealPlanPage() {
  const api = useApi()
  const [loaded, setLoaded] = useState(false)
  const [active, setActive] = useState<ActiveMealPlan | null>(null)
  const [proposal, setProposal] = useState<MealProposal | null>(null)
  const [busy, setBusy] = useState<'generating' | 'deciding' | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState<ApiError | null>(null)
  const [reloads, setReloads] = useState(0) // bump to load everything again (after approving)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.get<ActiveMealPlan>('/plans/meal/active').catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) return null // no plan yet is normal
        throw e
      }),
      api.get<{ proposals: MealProposal[] }>('/plans/proposals/pending'),
    ]).then(
      ([plan, pending]) => {
        if (cancelled) return
        setActive(plan)
        setProposal(pending.proposals.find((p) => p.type === 'meal_change') ?? null)
        setLoaded(true)
      },
      (e: unknown) => { if (!cancelled) setError(asApiError(e)) },
    )
    return () => {
      cancelled = true
    }
  }, [api, reloads])

  useEffect(() => {
    if (busy !== 'generating') return
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.round((Date.now() - started) / 1000)), 1000)
    return () => {
      clearInterval(timer)
      setSeconds(0)
    }
  }, [busy])

  async function run(kind: 'generating' | 'deciding', action: () => Promise<void>) {
    setBusy(kind)
    setError(null)
    try {
      await action()
    } catch (e) {
      setError(asApiError(e))
    } finally {
      setBusy(null)
    }
  }

  const generate = () => run('generating', async () => setProposal(await api.post<MealProposal>('/plans/meal/generate')))
  const approve = (id: string) => run('deciding', async () => {
    await api.post<MealProposal>(`/plans/proposals/${id}/approve`)
    setReloads((n) => n + 1)
  })
  const reject = (id: string) => run('deciding', async () => {
    await api.post<MealProposal>(`/plans/proposals/${id}/reject`)
    setProposal(null)
  })

  return (
    <PageShell title="Meal plan" back>
      {error && (
        <>
          <FormError message={error.message} requestId={error.requestId} />
          {error.status === 409 && <Link to="/onboarding" className="text-sm font-semibold text-brand-strong">Go to onboarding</Link>}
        </>
      )}
      {!loaded && !error && <p className="text-center text-sm text-muted">Loading…</p>}

      {loaded && proposal && (
        <section aria-label="Plan waiting for your approval" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm ring-2 ring-brand">
          <h2 className="text-base font-bold text-ink">New plan: approve it to make it yours</h2>
          <p className="text-sm text-ink-soft">{proposal.summary}</p>
          {proposal.payload.how_made && <HowMadePanel made={proposal.payload.how_made} />}
          {proposal.payload.days && <MealDays days={daysFromPayload(proposal.payload.days)} targets={proposal.payload.targets} />}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button" onClick={() => reject(proposal.id)} disabled={busy !== null}
              className="rounded-xl border border-line px-4 py-3 font-semibold text-ink-soft transition hover:bg-surface-2 disabled:opacity-50"
            >
              Reject
            </button>
            <PrimaryButton type="button" onClick={() => approve(proposal.id)} busy={busy === 'deciding'} disabled={busy !== null}>
              Approve
            </PrimaryButton>
          </div>
        </section>
      )}

      {loaded && !proposal && (
        <>
          {active ? (
            <section aria-label="Your meal plan" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm">
              <h2 className="text-base font-bold text-ink">Your plan</h2>
              {active.how_made && <HowMadePanel made={active.how_made} />}
              <MealDays days={active.days} targets={active.targets} />
            </section>
          ) : (
            <p className="text-sm text-ink-soft">
              You don&apos;t have a meal plan yet. The coach picks Indian dishes that fit your diet, our code works out the portions for your
              targets, and you see the plan first and decide.
            </p>
          )}
          <PrimaryButton type="button" onClick={generate} disabled={busy !== null}>
            {busy === 'generating' ? 'Building your plan…' : active ? 'Make me a new plan' : 'Generate my plan'}
          </PrimaryButton>
        </>
      )}
      {busy === 'generating' && (
        <p role="status" className="text-center text-sm text-muted">
          Building your 7 days of meals… this takes about a minute{seconds > 0 ? ` (${seconds} s so far)` : ''}. Please keep this page open.
        </p>
      )}
    </PageShell>
  )
}
