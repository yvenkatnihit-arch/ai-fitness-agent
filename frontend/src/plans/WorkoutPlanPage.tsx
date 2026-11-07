import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { FormError, PageShell, PrimaryButton } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { FocusPicker } from './FocusPicker'
import { PlanDays } from './PlanDays'
import type { ActivePlan, FocusState, Proposal } from './types'
import { words } from '../lib/words'

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))

// Your workout plan. A plan the coach builds is only a PROPOSAL until you press Approve; then it becomes your plan.
export function WorkoutPlanPage() {
  const api = useApi()
  const [loaded, setLoaded] = useState(false)
  const [active, setActive] = useState<ActivePlan | null>(null)
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [focus, setFocus] = useState<FocusState | null>(null)
  const [busy, setBusy] = useState<'generating' | 'deciding' | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  const [reloads, setReloads] = useState(0) // bump to load everything again (after approving)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.get<ActivePlan>('/plans/workout/active').catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) return null // no plan yet is normal
        throw e
      }),
      api.get<{ proposals: Proposal[] }>('/plans/proposals/pending'),
      api.get<FocusState>('/training/focus-areas').catch(() => null), // a bonus: the page works without it
    ]).then(
      ([plan, pending, chosen]) => {
        if (cancelled) return
        setActive(plan)
        setFocus(chosen)
        setProposal(pending.proposals.find((p) => p.type === 'workout_change') ?? null)
        setLoaded(true)
      },
      (e: unknown) => { if (!cancelled) setError(asApiError(e)) },
    )
    return () => {
      cancelled = true
    }
  }, [api, reloads])

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

  const saveFocus = (areas: string[]) => run('deciding', async () => {
    setFocus(await api.put<FocusState>('/training/focus-areas', { focus_areas: areas }))
  })
  const generate = () => run('generating', async () => setProposal(await api.post<Proposal>('/plans/workout/generate')))
  const approve = (id: string) => run('deciding', async () => {
    await api.post<Proposal>(`/plans/proposals/${id}/approve`)
    setReloads((n) => n + 1)
  })
  const reject = (id: string) => run('deciding', async () => {
    await api.post<Proposal>(`/plans/proposals/${id}/reject`)
    setProposal(null)
  })

  return (
    <PageShell title="Workout plan" back>
      {error && (
        <>
          <FormError message={error.message} requestId={error.requestId} />
          {error.status === 409 && (
            <div className="flex gap-4 text-sm font-semibold text-brand-strong">
              <Link to="/splits">Choose a split</Link>
              <Link to="/onboarding">Go to onboarding</Link>
            </div>
          )}
        </>
      )}
      {!loaded && !error && <p className="text-center text-sm text-muted">Loading…</p>}

      {loaded && proposal && (
        <section aria-label="Plan waiting for your approval" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm ring-2 ring-brand">
          <h2 className="text-base font-bold text-ink">New plan: approve it to make it yours</h2>
          <p className="text-sm text-ink-soft">{proposal.summary}</p>
          {proposal.payload.focus_areas && proposal.payload.focus_areas.length > 0 && (
            <p className="text-xs font-semibold text-brand-strong">Extra focus: {proposal.payload.focus_areas.map(words).join(', ')}</p>
          )}
          {proposal.payload.doctor_note && (
            <p className="rounded-lg bg-warn-soft p-3 text-xs text-warn">{proposal.payload.doctor_note}</p>
          )}
          {proposal.payload.days && <PlanDays days={proposal.payload.days} />}
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
            <section aria-label="Your workout plan" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm">
              <h2 className="text-base font-bold text-ink">Your plan</h2>
              <PlanDays days={active.days} />
            </section>
          ) : (
            <p className="text-sm text-ink-soft">
              You don&apos;t have a workout plan yet. The coach builds one from your split, your level, your equipment and your limits.
              You will see it first and decide.
            </p>
          )}
          {focus && <FocusPicker focus={focus} disabled={busy !== null} onChange={saveFocus} />}
          <PrimaryButton type="button" onClick={generate} disabled={busy !== null}>
            {busy === 'generating' ? 'Building your plan…' : active ? 'Make me a new plan' : 'Generate my plan'}
          </PrimaryButton>
        </>
      )}
      {busy === 'generating' && (
        <p role="status" className="text-center text-sm text-muted">Building your plan… this takes about 15 seconds.</p>
      )}
    </PageShell>
  )
}
