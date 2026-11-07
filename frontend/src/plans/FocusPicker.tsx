import { words } from '../lib/words'
import type { FocusState } from './types'

// "Muscles to bring up": tap up to two. The choice is saved straight away and used the next time a plan is made.
export function FocusPicker({ focus, disabled, onChange }: {
  focus: FocusState
  disabled: boolean
  onChange: (areas: string[]) => void
}) {
  const full = focus.focus_areas.length >= focus.max_areas
  function toggle(area: string) {
    const chosen = focus.focus_areas.includes(area)
    onChange(chosen ? focus.focus_areas.filter((a) => a !== area) : [...focus.focus_areas, area])
  }
  return (
    <fieldset className="flex flex-col gap-2 rounded-2xl bg-surface p-4 shadow-sm">
      <legend className="text-base font-bold text-ink">Muscles to bring up</legend>
      <p className="text-xs text-muted">
        Pick up to {focus.max_areas}. They get an extra exercise and extra sets, within safe limits. Used the next time you make a plan.
      </p>
      <div className="flex flex-wrap gap-2">
        {focus.options.map((area) => {
          const on = focus.focus_areas.includes(area)
          return (
            <button
              key={area} type="button" aria-pressed={on} disabled={disabled || (full && !on)} onClick={() => toggle(area)}
              className={`rounded-full border px-3 py-1.5 text-sm font-medium capitalize transition disabled:opacity-40 ${
                on ? 'border-brand bg-brand text-on-brand' : 'border-line text-ink-soft hover:bg-surface-2'
              }`}
            >
              {words(area)}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
