import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { expect, test } from 'vitest'

import type { WeightHistory } from '../weight/types'
import { GoalProgress } from './GoalProgress'
import { MealChecklist } from './MealChecklist'
import { checklistSlots, kcalLeft, nextPlannedMeal } from './mealSlots'
import { NextMealCard } from './NextMealCard'
import { TodayProgress } from './TodayProgress'
import type { Today } from './types'

const P = (eaten: number, target: number, percent: number) => ({ eaten, target, percent })
const item = (name: string) => ({ name, text: '1 katori (150 g)', kcal: 200 })
const TODAY: Today = {
  date: '2026-11-12', weekday: 'Thursday', numbers_hidden: false, workout: null,
  progress: { kcal: P(704, 1408, 50), protein_g: P(29, 116, 25), carbs_g: P(80, 148, 54), fat_g: P(20, 39, 51) },
  logged: [{ slot: 'breakfast', foods: ['Idli'] }],
  meal_plan: { kcal: 1400, meals: [
    { slot: 'dinner', items: [item('Khichdi')] }, { slot: 'breakfast', items: [item('Idli')] },
    { slot: 'lunch', items: [item('Dal'), item('Roti')] }, { slot: 'evening_snack', items: [item('Fruit')] },
  ] },
}
// A time in India (UTC+5:30) as an instant, the way the log screen's own tests do it.
const ist = (hhmm: string) => {
  const [h, m] = hhmm.split(':').map(Number)
  return new Date(Date.UTC(2026, 10, 12, h, m) - 330 * 60 * 1000)
}

test('calories left is one subtraction of the two server numbers, and over is said without blame', () => {
  expect(kcalLeft(704, 1408)).toEqual({ amount: 704, over: false })
  expect(kcalLeft(1500.4, 1408)).toEqual({ amount: 92, over: true })
  expect(kcalLeft(1408, 1408)).toEqual({ amount: 0, over: false })
  render(<MemoryRouter><TodayProgress today={TODAY} /></MemoryRouter>)
  expect(screen.getByLabelText('Calories left today')).toHaveTextContent('704 kcal left today')
  render(<MemoryRouter><TodayProgress today={{ ...TODAY, progress: { ...TODAY.progress!, kcal: P(1500, 1408, 107) } }} /></MemoryRouter>)
  expect(screen.getAllByLabelText('Calories left today')[1]).toHaveTextContent('92 kcal over today’s target')
})

test('the meals checklist follows the plan in day order, ticks what is logged and says so in words for screen readers', () => {
  expect(checklistSlots(TODAY)).toEqual(['breakfast', 'lunch', 'evening_snack', 'dinner'])
  render(<MealChecklist today={TODAY} />)
  const items = within(screen.getByRole('list', { name: 'Meals logged today' })).getAllByRole('listitem')
  expect(items.map((i) => i.textContent)).toEqual(['Breakfast (logged)', 'Lunch (not logged yet)', 'Evening snack (not logged yet)', 'Dinner (not logged yet)'])
  expect(items.map((i) => i.getAttribute('data-logged'))).toEqual(['true', 'false', 'false', 'false'])
})

test('without a meal plan the checklist shows the four everyday meals', () => {
  expect(checklistSlots({ ...TODAY, meal_plan: null })).toEqual(['breakfast', 'lunch', 'evening_snack', 'dinner'])
})

test('the next meal is the first planned one not logged and not passed, by the time of day', () => {
  expect(nextPlannedMeal(TODAY, ist('08:00'))?.slot).toBe('lunch')                  // breakfast is logged
  expect(nextPlannedMeal({ ...TODAY, logged: [] }, ist('08:00'))?.slot).toBe('breakfast')
  expect(nextPlannedMeal({ ...TODAY, logged: [] }, ist('13:00'))?.slot).toBe('lunch')
  expect(nextPlannedMeal({ ...TODAY, logged: [] }, ist('17:00'))?.slot).toBe('evening_snack')
  expect(nextPlannedMeal({ ...TODAY, logged: [] }, ist('21:00'))?.slot).toBe('dinner')
  expect(nextPlannedMeal({ ...TODAY, logged: [{ slot: 'dinner', foods: [] }] }, ist('21:00'))).toBeNull()
  expect(nextPlannedMeal({ ...TODAY, meal_plan: null }, ist('08:00'))).toBeNull()
})

test('the next-meal card shows the meal and what is in it, says when nothing is left, and is absent without a meal plan', () => {
  const { unmount } = render(<MemoryRouter><NextMealCard today={TODAY} now={ist('13:00')} /></MemoryRouter>)
  const card = screen.getByRole('region', { name: 'Next meal' })
  expect(card).toHaveTextContent('Lunch')
  expect(card).toHaveTextContent('Dal (1 katori (150 g)), Roti (1 katori (150 g))')
  expect(within(card).getByRole('link', { name: 'Log it when you eat' })).toHaveAttribute('href', '/log')
  unmount()
  render(<MemoryRouter><NextMealCard today={{ ...TODAY, logged: [{ slot: 'dinner', foods: [] }] }} now={ist('21:00')} /></MemoryRouter>)
  expect(screen.getByRole('region', { name: 'Next meal' })).toHaveTextContent('No more planned meals for today')
})

test('no meal plan means no next-meal card', () => {
  const { container } = render(<MemoryRouter><NextMealCard today={{ ...TODAY, meal_plan: null }} /></MemoryRouter>)
  expect(container).toBeEmptyDOMElement()
})

const WEIGHT: WeightHistory = {
  numbers_hidden: false, entries: [], latest_kg: 57, latest_on: '2026-11-11', start_weight_kg: 58, target_weight_kg: 54,
  change_since_start_kg: -1, kg_to_target: -3, percent_to_target: 25, weekly_change_kg: null,
}

test('goal progress shows the server percentage as a bar with start, now and target in words', () => {
  render(<GoalProgress history={WEIGHT} />)
  const bar = screen.getByRole('progressbar', { name: 'Goal progress' })
  expect(bar).toHaveAttribute('aria-valuenow', '25')
  expect(bar).toHaveAttribute('aria-valuetext', '25% of the way to your target weight')
  expect(screen.getByRole('region', { name: 'Goal progress' })).toHaveTextContent('Started at 58 kg, now 57 kg, target 54 kg.')
})

test('goal progress stays out of the way: nothing without a target or a weigh-in, nothing for users who must not see weights, and it never goes past 100', () => {
  for (const history of [
    null, { ...WEIGHT, numbers_hidden: true }, { ...WEIGHT, percent_to_target: null }, { ...WEIGHT, target_weight_kg: null }, { ...WEIGHT, latest_kg: null },
  ]) {
    const { container, unmount } = render(<GoalProgress history={history} />)
    expect(container).toBeEmptyDOMElement()
    unmount()
  }
  render(<GoalProgress history={{ ...WEIGHT, percent_to_target: 130 }} />)
  expect(screen.getByRole('progressbar', { name: 'Goal progress' })).toHaveAttribute('aria-valuenow', '100')
})
