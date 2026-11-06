import { words, type Exercise } from './types'

const LEVEL_STYLE: Record<string, string> = {
  beginner: 'bg-brand-soft text-brand-strong',
  intermediate: 'bg-warn-soft text-warn',
  advanced: 'bg-danger-soft text-danger',
}

export function ExerciseCard({ exercise }: { exercise: Exercise }) {
  const [main, ...others] = exercise.muscle_groups
  return (
    <li className="rounded-xl bg-surface p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{exercise.name}</h3>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${LEVEL_STYLE[exercise.difficulty] ?? ''}`}>
          {exercise.difficulty}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted">
        <span className="font-medium text-ink-soft">{words(main)}</span>
        {others.length > 0 && ` + ${others.map(words).join(', ')}`}
        {' · '}
        {exercise.equipment.length === 0 ? 'No equipment' : exercise.equipment.map(words).join(', ')}
      </p>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs font-medium text-brand-strong">How to do it</summary>
        <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">
          {exercise.form_cues.map((cue) => <li key={cue}>{cue}</li>)}
        </ul>
      </details>
    </li>
  )
}
