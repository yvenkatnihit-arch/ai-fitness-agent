import { words } from '../lib/words'

export type ExerciseChoice = {
  key: string
  name: string
  muscle_groups: string[]
  difficulty: string
  movement_pattern: string
}

// The valid choices the server offered for a swap or an add. Only these can be picked, so a pick is always accepted
// (the server still checks it again).
export function ExercisePicker({ title, options, busy, onPick, onCancel }: {
  title: string
  options: ExerciseChoice[] | null // null = still loading
  busy: boolean
  onPick: (key: string) => void
  onCancel: () => void
}) {
  return (
    <section aria-label={title} className="mt-2 flex flex-col gap-2 rounded-lg border border-brand bg-surface p-3">
      <h4 className="text-xs font-bold uppercase tracking-wide text-muted">{title}</h4>
      {options === null && <p className="text-xs text-muted">Loading…</p>}
      {options !== null && options.length === 0 && <p className="text-xs text-muted">No other exercise fits here with your equipment and limits.</p>}
      {options !== null && options.length > 0 && (
        <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto">
          {options.map((o) => (
            <li key={o.key}>
              <button
                type="button" disabled={busy} onClick={() => onPick(o.key)}
                className="w-full rounded-lg border border-line px-3 py-2 text-left text-sm transition hover:bg-surface-2 disabled:opacity-50"
              >
                <span className="font-semibold text-ink">{o.name}</span>
                <span className="block text-xs text-muted">{o.muscle_groups.map(words).join(', ')} · {o.difficulty}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <button type="button" onClick={onCancel} className="self-start text-xs font-semibold text-brand-strong">Cancel</button>
    </section>
  )
}
