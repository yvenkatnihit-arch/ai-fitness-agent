import { words, type Exercise } from './types'

const LEVEL_STYLE: Record<string, string> = {
  beginner: 'bg-emerald-50 text-emerald-800',
  intermediate: 'bg-amber-50 text-amber-800',
  advanced: 'bg-rose-50 text-rose-800',
}

export function ExerciseCard({ exercise }: { exercise: Exercise }) {
  const [main, ...others] = exercise.muscle_groups
  return (
    <li className="rounded-xl bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">{exercise.name}</h3>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${LEVEL_STYLE[exercise.difficulty] ?? ''}`}>
          {exercise.difficulty}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        <span className="font-medium text-slate-700">{words(main)}</span>
        {others.length > 0 && ` + ${others.map(words).join(', ')}`}
        {' · '}
        {exercise.equipment.length === 0 ? 'No equipment' : exercise.equipment.map(words).join(', ')}
      </p>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs font-medium text-emerald-700">How to do it</summary>
        <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
          {exercise.form_cues.map((cue) => <li key={cue}>{cue}</li>)}
        </ul>
      </details>
    </li>
  )
}
