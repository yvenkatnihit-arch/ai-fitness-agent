import { Activity, CalendarDays, Dumbbell, Flame, Salad, TrendingUp, Utensils, type LucideIcon } from 'lucide-react'

import { SUGGESTIONS } from './suggestions'

// One icon per starter question (matched by its label). Decorative only: the button's name is still the label.
const ICONS: Record<string, LucideIcon> = {
  'Protein in paneer': Flame,
  'High-protein foods': Salad,
  "Today's workout": Dumbbell,
  "Tomorrow's lunch": CalendarDays,
  'Am I on track?': TrendingUp,
  'How to do a plank': Activity,
  'Log a meal': Utensils,
}

// The empty chat: the example questions as tappable cards (what the coach can do, in one glance).
export function PromptCards({ disabled, onPick }: { disabled: boolean; onPick: (message: string) => void }) {
  return (
    <ul aria-label="Example questions" className="grid grid-cols-2 gap-2">
      {SUGGESTIONS.map((s) => {
        const Icon = ICONS[s.label] ?? Flame
        return (
          <li key={s.label}>
            <button
              type="button" title={s.message} disabled={disabled} onClick={() => onPick(s.message)}
              className="glass flex h-full w-full items-center gap-2 rounded-2xl p-3 text-left text-sm font-medium text-ink transition hover:border-brand disabled:opacity-50"
            >
              <Icon aria-hidden="true" size={18} className="shrink-0 text-brand-strong" />
              {s.label}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
