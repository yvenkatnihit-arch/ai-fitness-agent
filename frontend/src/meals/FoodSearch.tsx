import { useEffect, useState } from 'react'

import { inputClass } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import type { FoodHit } from './types'

const DEBOUNCE_MS = 300 // wait until the user pauses typing before searching
const MIN_CHARS = 2

// Search box + results. Calls onPick with the chosen food.
export function FoodSearch({ onPick }: { onPick: (food: FoodHit) => void }) {
  const api = useApi()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<FoodHit[]>([])
  const [error, setError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)

  const trimmed = query.trim()
  const active = trimmed.length >= MIN_CHARS

  useEffect(() => {
    if (!active) return
    let cancelled = false
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const hits = await api.get<FoodHit[]>(`/foods/search?q=${encodeURIComponent(trimmed)}&limit=8`)
        if (!cancelled) {
          setResults(hits)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Search failed. Please try again.')
      } finally {
        if (!cancelled) setSearching(false)
      }
    }, DEBOUNCE_MS)
    return () => {
      cancelled = true // a newer keystroke replaces this search
      clearTimeout(timer)
    }
  }, [api, trimmed, active])

  const shown = active ? results : []

  return (
    <div className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
        Search food
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. roti, dal, chawal, idli"
          className={inputClass}
          autoComplete="off"
        />
      </label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {active && !searching && !error && shown.length === 0 && (
        <p className="text-sm text-slate-500">No foods found. Try another name.</p>
      )}
      {shown.length > 0 && (
        <ul aria-label="Search results" className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {shown.map((food) => (
            <li key={food.id}>
              <button
                type="button"
                onClick={() => {
                  onPick(food)
                  setQuery('')
                  setResults([])
                }}
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50"
              >
                <span>
                  <span className="block text-sm font-medium text-slate-800">{food.name}</span>
                  {!food.verified && <span className="block text-xs text-amber-700">values being checked</span>}
                </span>
                <span className="shrink-0 text-xs text-slate-500">{Math.round(food.kcal_per_100g)} kcal / 100 g</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
