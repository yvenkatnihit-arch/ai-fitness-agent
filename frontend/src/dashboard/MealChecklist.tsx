import { Check } from 'lucide-react'

import { checklistSlots, loggedSlots, slotLabel } from './mealSlots'
import type { Today } from './types'

// Which of today's meals are logged: a lime tick for each one done. No numbers, so it is shown to everyone.
export function MealChecklist({ today }: { today: Today }) {
  const done = loggedSlots(today)
  return (
    <ul aria-label="Meals logged today" className="flex flex-wrap justify-center gap-2">
      {checklistSlots(today).map((slot) => {
        const logged = done.has(slot)
        return (
          <li
            key={slot} data-logged={logged}
            className={`flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${
              logged ? 'border-brand bg-brand-soft text-brand-strong' : 'border-line text-muted'
            }`}
          >
            {logged && <Check aria-hidden="true" size={12} />}
            {slotLabel(slot)}
            <span className="sr-only">{logged ? ' (logged)' : ' (not logged yet)'}</span>
          </li>
        )
      })}
    </ul>
  )
}
