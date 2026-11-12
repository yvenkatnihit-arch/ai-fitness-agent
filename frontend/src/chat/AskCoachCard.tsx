import { Link } from 'react-router'

import { SUGGESTIONS } from './suggestions'

// Starter questions on Home. Each one opens the chat and asks it at once, so a first-time visitor sees what the coach can do in one tap.
const STARTERS = [SUGGESTIONS[0], SUGGESTIONS[2], SUGGESTIONS[4], SUGGESTIONS[6]]

export function AskCoachCard() {
  return (
    <section aria-label="Ask the coach" className="flex flex-col gap-2 rounded-2xl bg-surface p-4 shadow-sm">
      <h2 className="text-base font-bold text-ink">Ask the coach</h2>
      <p className="text-xs text-muted">Foods, exercises, your plan and progress, or tell it what you ate. Tap one to try it.</p>
      <ul aria-label="Starter questions" className="flex flex-wrap gap-2">
        {STARTERS.map((s) => (
          <li key={s.label}>
            <Link
              to={`/chat?ask=${encodeURIComponent(s.message)}`} title={s.message}
              className="inline-block rounded-full border border-brand bg-brand-soft px-3 py-1.5 text-sm font-medium text-brand-strong transition hover:opacity-90"
            >
              {s.label}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
