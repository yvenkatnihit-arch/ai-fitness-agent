import type { ChatMeta } from './types'

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

// "How this answer was made": which specialists ran and what they used. Names and counts only (the server never sends the model's text here).
export function AnswerDetails({ meta }: { meta: ChatMeta }) {
  const runs = meta.specialists ?? []
  if (runs.length === 0) return null // a guard message or "nothing fits": nothing ran
  return (
    <details className="text-xs text-muted">
      <summary className="cursor-pointer">How this answer was made</summary>
      <ul className="mt-1 flex flex-col gap-1">
        {runs.map((run) => (
          <li key={run.name}>
            {run.name}: {run.status === 'ok' ? 'answered' : 'could not finish'} in {plural(run.steps, 'step')}, {run.tokens.toLocaleString('en-US')} tokens
            {run.tools.length > 0 && `, used ${[...new Set(run.tools)].join(', ')}`}
          </li>
        ))}
        {runs.length > 1 && <li>{meta.composed ? 'The answers were merged into one reply.' : 'The answers are shown one after the other.'}</li>}
      </ul>
    </details>
  )
}
