import { screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from '../App'
import type { Today } from '../dashboard/types'
import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'

afterEach(() => vi.unstubAllGlobals())

const TARGETS = {
  calorie_target_kcal: 1408, protein_g: 116, fat_g: 39, carbs_g: 148, protein_pct: 33, carbs_pct: 42, fat_pct: 25,
  reasons: [], doctor_note: null, focus_on_habits: false,
}
const FORECAST = { status: 'no_target', message: 'Set a target weight to see a goal date.', current_weight_kg: null, target_weight_kg: null,
  weekly_change_kg: null, earliest: null, likely: null, latest: null, weeks_likely: null, note: null }
const WEIGHT = {
  numbers_hidden: false, latest_kg: 57, latest_on: '2026-11-11', start_weight_kg: 58, target_weight_kg: 54,
  change_since_start_kg: -1, kg_to_target: -3, percent_to_target: 25, weekly_change_kg: -1.75,
  entries: [{ date: '2026-11-01', weight_kg: 58 }, { date: '2026-11-11', weight_kg: 57 }],
}
const P = (eaten: number, target: number, percent: number) => ({ eaten, target, percent })
const TODAY: Today = {
  date: '2026-11-12', weekday: 'Thursday', numbers_hidden: false,
  progress: { kcal: P(704, 1408, 50), protein_g: P(29, 116, 25), carbs_g: P(80, 148, 54), fat_g: P(20, 39, 51) },
  logged: [{ slot: 'lunch', foods: ['Roti'] }],
  meal_plan: { kcal: 1400, meals: [{ slot: 'breakfast', items: [{ name: 'Idli', text: '4 pieces', kcal: 232 }] }] },
  workout: { rest_day: true, focus: null, minutes: null, exercises: [] },
}

function renderHome() {
  fakeFetch({
    'GET /onboarding/status': { body: status('done', [], true) },
    'GET /targets/current': { body: TARGETS },
    'GET /targets/forecast': { body: FORECAST },
    'GET /dashboard/today': { body: TODAY },
    'GET /weight': { body: WEIGHT },
  })
  renderWithAuth(fakeAuth({ session: fakeSession('kruthi@example.test') }), { '*': <App /> }, '/')
}

test('Home has four panes in this order: Today, Targets, Plan, Weight', async () => {
  renderHome()
  await screen.findByRole('region', { name: "Today's progress" })
  expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Today', 'Targets', 'Plan', 'Weight'])
  expect(screen.getByRole('tab', { name: 'Today' })).toHaveAttribute('aria-selected', 'true')       // it opens on the dashboard
})

test('the Today pane is only the dashboard: greeting, ring, macros, insight and what was logged', async () => {
  renderHome()
  const today = await screen.findByRole('tabpanel', { name: 'Today' })
  expect(within(today).getByRole('region', { name: "Today's progress" })).toBeInTheDocument()
  expect(within(today).getByRole('progressbar', { name: 'Calories eaten today' })).toBeInTheDocument()
  expect(within(today).getByRole('region', { name: "Today's insight" })).toBeInTheDocument()
  for (const other of [/Weight/, /Ask the coach/, /Today's meals/, /Today's workout/, /Log a meal/, /Daily targets|Your daily targets/i]) {
    expect(within(today).queryByRole('region', { name: other })).not.toBeInTheDocument()
  }
  expect(within(today).getByRole('link', { name: 'Log another meal' })).toHaveAttribute('href', '/log')              // the small button under what was logged
  expect(within(today).queryByText('1,408')).not.toBeInTheDocument()                                   // the targets are on their own pane
})

test('each other pane holds its own cards', async () => {
  renderHome()
  await screen.findByRole('tabpanel', { name: 'Today' })
  expect(within(screen.getByRole('tabpanel', { name: 'Targets' })).getByText('1,408')).toBeInTheDocument()
  const plan = screen.getByRole('tabpanel', { name: 'Plan' })
  expect(within(plan).getByRole('region', { name: "Today's meals" })).toBeInTheDocument()
  expect(within(plan).getByRole('region', { name: 'Ask the coach' })).toBeInTheDocument()
  // "Log a meal" is also a starter question for the coach, so look at where the links go: one goes to the log screen.
  expect(within(plan).getAllByRole('link', { name: 'Log a meal' }).map((l) => l.getAttribute('href'))).toContain('/log')
  expect(within(plan).getByRole('link', { name: 'Workout plan' })).toHaveAttribute('href', '/workout')
  expect(await within(screen.getByRole('tabpanel', { name: 'Weight' })).findByRole('region', { name: 'Weight' })).toBeInTheDocument()     // the weight history loads after the page
})
