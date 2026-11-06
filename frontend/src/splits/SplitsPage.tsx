import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { FormError, PageShell } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { SplitCard } from './SplitCard'
import { GOAL_LABEL, type SplitRecommendations } from './types'

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))

// Pick how your training week is divided. The options and the reasons come from the backend's rules
// (no LLM); this screen only shows them and saves the choice.
export function SplitsPage() {
  const api = useApi()
  const [data, setData] = useState<SplitRecommendations | null>(null)
  const [chosen, setChosen] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    let cancelled = false
    api.get<SplitRecommendations>('/splits/recommend').then(
      (loaded) => { if (!cancelled) { setData(loaded); setChosen(loaded.chosen_key) } },
      (e: unknown) => { if (!cancelled) setError(asApiError(e)) },
    )
    return () => {
      cancelled = true
    }
  }, [api])

  async function choose(key: string) {
    setSaving(true)
    setError(null)
    try {
      await api.put<{ split_key: string }>('/splits/choice', { split_key: key })
      setChosen(key)
    } catch (e) {
      setError(asApiError(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <PageShell title="Workout split" back>
      {error && (
        <>
          <FormError message={error.message} requestId={error.requestId} />
          {error.status === 409 && <Link to="/onboarding" className="text-sm font-semibold text-brand-strong">Go to onboarding</Link>}
        </>
      )}
      {!error && !data && <p className="text-center text-sm text-muted">Loading…</p>}
      {data && (
        <>
          <p className="text-sm text-ink-soft">
            You train {data.days_per_week} {data.days_per_week === 1 ? 'day' : 'days'} a week at {data.level} level,
            aiming for {GOAL_LABEL[data.goal] ?? data.goal}. Here is how the week can be divided, best match first.
          </p>
          <ul aria-label="Splits" className="flex flex-col gap-4">
            {data.recommendations.map((rec) => (
              <SplitCard key={rec.key} rec={rec} chosen={chosen === rec.key} saving={saving} onChoose={choose} />
            ))}
          </ul>
        </>
      )}
    </PageShell>
  )
}
