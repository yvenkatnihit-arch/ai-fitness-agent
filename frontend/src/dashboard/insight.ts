import type { Today } from './types'

// The insight card (D-059): rules over today's numbers, written in code. No AI call, so it is free, instant and always matches the
// screen. The percentages come from the server. The wording never pushes anyone to eat less.
export function insightFor(today: Today): string | null {
  const p = today.progress
  if (!p || today.numbers_hidden) return null
  if (today.logged.length === 0 && p.kcal.eaten === 0) return 'Nothing logged yet today. Log your first meal and the ring starts to fill.'
  if (p.kcal.percent > 100) return 'You are past today’s calorie target. Log what you eat anyway: honest numbers make your trend useful.'
  if (p.protein_g.percent >= 100) return 'Protein target reached for today. That is the number that matters most for your goal.'
  if (p.protein_g.percent < 50 && p.kcal.percent >= 60) {
    return `Protein is at ${p.protein_g.percent}% while calories are at ${p.kcal.percent}%. A protein food at your next meal would balance the day.`
  }
  return `Protein is at ${p.protein_g.percent}% of today’s target.`
}
