import { render, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'

import { CalorieRing } from './CalorieRing'
import { InsightCard } from './InsightCard'
import { insightFor } from './insight'
import { MacroCards } from './MacroCards'
import type { Today } from './types'

const P = (eaten: number, target: number, percent: number) => ({ eaten, target, percent })
const TODAY: Today = {
  date: '2026-11-12', weekday: 'Thursday', numbers_hidden: false, meal_plan: null, workout: null,
  logged: [{ slot: 'lunch', foods: ['Roti'] }],
  progress: { kcal: P(704, 1408, 50), protein_g: P(29, 116, 25), carbs_g: P(80, 148, 54), fat_g: P(20, 39, 51) },
}
const withProgress = (over: Partial<NonNullable<Today['progress']>>): Today => ({ ...TODAY, progress: { ...TODAY.progress!, ...over } })

test('the calorie ring is a progress bar with the server percentage, the exact figures in text, and its fill drawn from that percentage', () => {
  render(<CalorieRing value={P(704, 1408, 50)} />)
  const ring = screen.getByRole('progressbar', { name: 'Calories eaten today' })
  expect(ring).toHaveAttribute('aria-valuenow', '50')
  expect(ring).toHaveAttribute('aria-valuetext', '50% of your calorie target')
  expect(ring).toHaveTextContent('704 / 1408 kcal')
  const fill = ring.querySelectorAll('circle')[1]
  const circumference = Number(fill.getAttribute('stroke-dasharray'))
  expect(Number(fill.getAttribute('stroke-dashoffset'))).toBeCloseTo(circumference / 2, 3)        // half the ring is empty at 50%
})

test('over the target the ring is full and turns amber, never beyond 100', () => {
  render(<CalorieRing value={P(1700, 1408, 121)} />)
  const ring = screen.getByRole('progressbar', { name: 'Calories eaten today' })
  expect(ring).toHaveAttribute('aria-valuenow', '100')
  expect(ring).toHaveAttribute('data-state', 'over')
  expect(ring.querySelectorAll('circle')[1].getAttribute('stroke-dashoffset')).toBe('0')
})

test('protein comes first and the macro cards show eaten against target with a bar each', () => {
  render(<MacroCards progress={TODAY.progress!} />)
  const bars = screen.getAllByRole('progressbar')
  expect(bars.map((b) => b.getAttribute('aria-label'))).toEqual(['Protein eaten today', 'Carbs eaten today', 'Fat eaten today'])
  expect(within(bars[0].parentElement!).getByText('Protein')).toBeInTheDocument()
  expect(bars[0].parentElement).toHaveTextContent('29 / 116 g')
})

test('insight rules: nothing logged, over the target, protein reached, protein behind and the default', () => {
  expect(insightFor({ ...TODAY, logged: [], progress: { ...TODAY.progress!, kcal: P(0, 1408, 0) } })).toMatch(/Nothing logged yet/)
  expect(insightFor(withProgress({ kcal: P(1600, 1408, 114) }))).toMatch(/past today’s calorie target/)
  expect(insightFor(withProgress({ protein_g: P(120, 116, 103) }))).toMatch(/Protein target reached/)
  expect(insightFor(withProgress({ kcal: P(900, 1408, 64), protein_g: P(30, 116, 26) }))).toBe(
    'Protein is at 26% while calories are at 64%. A protein food at your next meal would balance the day.')
  expect(insightFor(TODAY)).toBe('Protein is at 25% of today’s target.')
})

test('the insight never tells anyone to eat less, and users who must not see numbers get no insight card', () => {
  expect(insightFor(withProgress({ kcal: P(2000, 1408, 142) }))).not.toMatch(/\b(eat less|reduce|cut|stop eating|skip)\b/i)
  const hidden: Today = { ...TODAY, numbers_hidden: true, progress: null }
  expect(insightFor(hidden)).toBeNull()
  const { container } = render(<InsightCard today={hidden} />)
  expect(container).toBeEmptyDOMElement()
})
