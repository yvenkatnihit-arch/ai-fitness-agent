import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { FormError, PageShell } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { ExerciseCard } from './ExerciseCard'
import { words, type ExerciseList, type Setting } from './types'

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))

// The exercises this user can do. The backend already hides anything that doesn't fit their level, place,
// equipment or injuries (D-041, Step 5.4); this screen only lets them browse what is left.
export function ExercisesPage() {
  const api = useApi()
  const [wanted, setWanted] = useState<Setting | null>(null) // null = the setting from their onboarding answers
  const [list, setList] = useState<ExerciseList | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [muscle, setMuscle] = useState('all')
  const [text, setText] = useState('')

  useEffect(() => {
    let cancelled = false
    api.get<ExerciseList>(wanted ? `/exercises/for-me?setting=${wanted}` : '/exercises/for-me').then(
      (loaded) => { if (!cancelled) { setList(loaded); setError(null) } },
      (e: unknown) => { if (!cancelled) setError(asApiError(e)) },
    )
    return () => {
      cancelled = true
    }
  }, [api, wanted])

  const muscles = useMemo(
    () => [...new Set((list?.exercises ?? []).map((e) => e.muscle_groups[0]))].sort(),
    [list],
  )
  const visible = (list?.exercises ?? []).filter(
    (e) => (muscle === 'all' || e.muscle_groups[0] === muscle) && e.name.toLowerCase().includes(text.trim().toLowerCase()),
  )

  return (
    <PageShell title="Exercise library" back>

        {error && (
          <>
            <FormError message={error.message} requestId={error.requestId} />
            {error.status === 409 && <Link to="/onboarding" className="text-sm font-medium text-brand-strong">Go to onboarding</Link>}
          </>
        )}
        {!error && !list && <p className="text-center text-sm text-muted">Loading…</p>}

        {list && (
          <>
            <div role="group" aria-label="Where do you train?" className="grid grid-cols-2 gap-2">
              {(['gym', 'home'] as Setting[]).map((place) => (
                <button
                  key={place}
                  type="button"
                  aria-pressed={list.setting === place}
                  onClick={() => { setWanted(place); setMuscle('all') }}
                  className={`rounded-lg border px-3 py-2 text-sm font-semibold capitalize ${
                    list.setting === place ? 'border-brand bg-brand text-on-brand' : 'border-line bg-surface text-ink-soft'
                  }`}
                >
                  {place}
                </button>
              ))}
            </div>

            <p className="text-sm text-muted">
              Showing {list.shown} of {list.total_in_library} exercises for the {list.setting}, {list.level} level.
              {list.injuries.length > 0 && ` Left out because of your ${list.injuries.map(words).join(', ')}.`}
            </p>
            {list.exercises.some((e) => !e.verified) && (
              <p className="rounded-lg bg-warn-soft p-3 text-xs text-warn">
                The safety tags on these exercises are still being reviewed. If anything hurts, stop. Sharp pain,
                swelling or numbness means see a doctor or physiotherapist.
              </p>
            )}

            <input
              aria-label="Search exercises"
              placeholder="Search by name"
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="rounded-lg border border-line bg-surface px-3 py-2 text-sm"
            />
            <div role="group" aria-label="Muscle" className="flex flex-wrap gap-2">
              {['all', ...muscles].map((m) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={muscle === m}
                  onClick={() => setMuscle(m)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${
                    muscle === m ? 'border-ink bg-ink text-on-brand' : 'border-line bg-surface text-ink-soft'
                  }`}
                >
                  {words(m)}
                </button>
              ))}
            </div>

            {visible.length === 0 ? (
              <p className="text-center text-sm text-muted">No exercises match.</p>
            ) : (
              <ul aria-label="Exercises" className="flex flex-col gap-3">
                {visible.map((e) => <ExerciseCard key={e.id} exercise={e} />)}
              </ul>
            )}
          </>
        )}
    </PageShell>
  )
}
