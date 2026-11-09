import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch } from '../test/fakeFetch'
import { MealPlanPage } from './MealPlanPage'
import type { ActiveMealPlan, HowMade, MealProposal } from './mealTypes'

afterEach(() => vi.unstubAllGlobals())

const MADE: HowMade = {
  days_from_model: 4, days_from_code: 3, sources: ['model', 'model', 'fallback', 'model', 'fallback', 'model', 'fallback'],
  meals_per_day: 4, repair_round: true, thin_roles: {}, checks: ['Every dish comes from our food database and fits your diet and dislikes.'],
  generation: { model_calls: 2, input_tokens: 4000, output_tokens: 10000, cost_usd: 0.0431, latency_ms: 41000 },
  days_ok: 2, days_with_issues: 5, average_percent_of_target: { kcal: 100, protein: 72, carbs: 120, fat: 101 },
}

const ITEMS = [
  { slot: 'breakfast', position: 1, name: 'Idli', text: '4 pieces (160 g)', grams: 160, kcal: 232 },
  { slot: 'lunch', position: 1, name: 'Roti', text: '2 pieces (86 g)', grams: 86, kcal: 174 },
  { slot: 'lunch', position: 2, name: 'Toor dal', text: '1.5 katori (188 g)', grams: 188, kcal: 200 },
]

const PROPOSAL: MealProposal = {
  id: 'm1', type: 'meal_change', source: 'plan_generation', status: 'pending', created_at: '2026-11-09T10:00:00Z',
  summary: '7-day vegetarian meal plan, 4 meals a day, about 1408 kcal a day, starting 2026-11-16.',
  payload: {
    week_start: '2026-11-16', numbers_hidden: false, targets: { kcal: 1408, protein_g: 116, carbs_g: 148, fat_g: 39 }, how_made: MADE,
    days: [{ day_of_week: 1, totals: { kcal: 606, protein_g: 30, carbs_g: 90, fat_g: 10 }, items: ITEMS }],
  },
}

const ACTIVE: ActiveMealPlan = {
  id: 'a1', week_start: '2026-11-16', version: 1, approved_at: '2026-11-09T10:05:00Z', numbers_hidden: false,
  targets: { kcal: 1408, protein_g: 116, carbs_g: 148, fat_g: 39 }, how_made: MADE,
  days: [{
    day_of_week: 2, totals: { kcal: 400, protein_g: 20, carbs_g: 60, fat_g: 8 },
    meals: [{ slot: 'dinner', items: [{ position: 1, name: 'Khichdi', text: '150 g', grams: 150, kcal: 200 }] }],
  }],
}

const NO_PLAN = { status: 404, body: { detail: "You don't have a meal plan yet." } }
const NO_PENDING = { body: { proposals: [] } }
const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/meal-plan': <MealPlanPage />, '/': <p>home</p>, '/onboarding': <p>onboarding</p> }, '/meal-plan')

test('with no plan yet it explains and offers to generate one', async () => {
  fakeFetch({ 'GET /plans/meal/active': NO_PLAN, 'GET /plans/proposals/pending': NO_PENDING })
  render()
  expect(await screen.findByText(/You don't have a meal plan yet/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Generate my plan' })).toBeEnabled()
})

test('generating shows a minute-long waiting message, then the proposal with Approve and Reject', async () => {
  let finish: () => void = () => {}
  const slow = new Promise<void>((resolve) => { finish = resolve })
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const { pathname } = new URL(url)
    const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
    if (pathname === '/plans/meal/active') return reply(NO_PLAN.body, 404)
    if (pathname === '/plans/proposals/pending') return reply({ proposals: [] })
    if (init.method === 'POST' && pathname === '/plans/meal/generate') {
      await slow
      return reply(PROPOSAL)
    }
    throw new Error(`unexpected ${pathname}`)
  }))
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Generate my plan' }))
  expect(await screen.findByRole('status')).toHaveTextContent('about a minute')
  expect(screen.getByRole('button', { name: 'Building your plan…' })).toBeDisabled()
  finish()
  const card = await screen.findByRole('region', { name: 'Plan waiting for your approval' })
  expect(within(card).getByRole('button', { name: 'Approve' })).toBeEnabled()
  expect(screen.queryByRole('region', { name: 'Your meal plan' })).not.toBeInTheDocument()   // a proposal is not your plan
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test('the proposal shows the week by meal, the numbers, and the how-this-was-made panel', async () => {
  fakeFetch({ 'GET /plans/meal/active': NO_PLAN, 'GET /plans/proposals/pending': { body: { proposals: [PROPOSAL] } } })
  render()
  const card = await screen.findByRole('region', { name: 'Plan waiting for your approval' })
  expect(within(card).getByText(PROPOSAL.summary)).toBeInTheDocument()
  expect(within(card).getByText(/Monday/)).toBeInTheDocument()
  expect(within(card).getByText(/606 kcal · P 30 · C 90 · F 10 \(target 1408 kcal\)/)).toBeInTheDocument()
  const lunch = within(card).getByRole('region', { name: 'Monday Lunch' })
  expect(within(lunch).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Roti 2 pieces (86 g)174 kcal', 'Toor dal 1.5 katori (188 g)200 kcal'])
  expect(within(card).getByText('4 days chosen by the AI coach and 3 days by our rule-based planner.')).toBeInTheDocument()
  expect(within(card).getByText(/AI: 2 calls, 14,000 tokens, about \$0.04, 41 s\./)).toBeInTheDocument()
  expect(within(card).getByText('The AI was asked once to fix days that missed your targets.')).toBeInTheDocument()
  expect(within(card).getByText(/reaches 100% of your calories, 72% of your protein/)).toBeInTheDocument()
  expect(within(card).getByText(/5 days of 7 have at least one number off target/)).toBeInTheDocument()
  expect(within(card).getByText(/✓ Every dish comes from our food database/)).toBeInTheDocument()
})

test('when the AI could not help, the panel says the planner did everything and notes thin choices', async () => {
  const code: HowMade = { ...MADE, days_from_model: 0, days_from_code: 7, generation: null, repair_round: false, thin_roles: { lunch: ['side'], dinner: ['side'] } }
  fakeFetch({ 'GET /plans/meal/active': NO_PLAN, 'GET /plans/proposals/pending': { body: { proposals: [{ ...PROPOSAL, payload: { ...PROPOSAL.payload, how_made: code } }] } } })
  render()
  expect(await screen.findByText(/All 7 days were planned by our rule-based planner/)).toBeInTheDocument()
  expect(screen.getByText(/Limited choice at Lunch and Dinner with your diet, so some dishes repeat/)).toBeInTheDocument()
  expect(screen.queryByText(/AI: /)).not.toBeInTheDocument()
})

test('approving saves it and then shows it as your plan', async () => {
  let approved = false
  const calls = fakeFetch({
    'GET /plans/meal/active': () => (approved ? { body: ACTIVE } : NO_PLAN),
    'GET /plans/proposals/pending': () => ({ body: { proposals: approved ? [] : [PROPOSAL] } }),
    'POST /plans/proposals/m1/approve': () => { approved = true; return { body: { ...PROPOSAL, status: 'approved' } } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  const plan = await screen.findByRole('region', { name: 'Your meal plan' })
  expect(within(plan).getByText('Khichdi')).toBeInTheDocument()
  expect(within(plan).getByText(/400 kcal · P 20 · C 60 · F 8 \(target 1408 kcal\)/)).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Plan waiting for your approval' })).not.toBeInTheDocument()
  expect(calls.some((c) => c.method === 'POST' && c.path === '/plans/proposals/m1/approve')).toBe(true)
})

test('rejecting removes the proposal and keeps the current plan', async () => {
  fakeFetch({
    'GET /plans/meal/active': { body: ACTIVE },
    'GET /plans/proposals/pending': { body: { proposals: [PROPOSAL] } },
    'POST /plans/proposals/m1/reject': { body: { ...PROPOSAL, status: 'rejected' } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
  expect(await screen.findByRole('region', { name: 'Your meal plan' })).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Plan waiting for your approval' })).not.toBeInTheDocument()
})

test('a user with a plan can ask for a new one', async () => {
  fakeFetch({ 'GET /plans/meal/active': { body: ACTIVE }, 'GET /plans/proposals/pending': NO_PENDING })
  render()
  expect(await screen.findByRole('button', { name: 'Make me a new plan' })).toBeEnabled()
})

test('for a user who must not see numbers the page shows portions and no calories or macros at all', async () => {
  const hiddenMade: HowMade = { ...MADE, days_ok: undefined, days_with_issues: undefined, average_percent_of_target: undefined }
  const hidden: MealProposal = {
    ...PROPOSAL, summary: '7-day vegetarian meal plan with balanced meals, 4 meals a day, starting 2026-11-16.',
    payload: { week_start: '2026-11-16', numbers_hidden: true, how_made: hiddenMade,
      days: [{ day_of_week: 1, items: ITEMS.map(({ kcal: _kcal, ...rest }) => rest) }] },
  }
  fakeFetch({ 'GET /plans/meal/active': NO_PLAN, 'GET /plans/proposals/pending': { body: { proposals: [hidden] } } })
  render()
  expect(await screen.findByText(/balanced meals/)).toBeInTheDocument()
  expect(screen.getByText('4 pieces (160 g)')).toBeInTheDocument()
  expect(screen.queryByText(/kcal/)).not.toBeInTheDocument()
  expect(screen.queryByText(/protein/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/of your calories/)).not.toBeInTheDocument()
})

test("a refusal such as 'finish onboarding' shows the message and a way back", async () => {
  fakeFetch({
    'GET /plans/meal/active': NO_PLAN, 'GET /plans/proposals/pending': NO_PENDING,
    'POST /plans/meal/generate': { status: 409, body: { detail: 'Please finish onboarding first.' } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Generate my plan' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Please finish onboarding first.')
  expect(screen.getByRole('link', { name: 'Go to onboarding' })).toBeInTheDocument()
})

test('a busy coach (503) shows the friendly message and the button works again', async () => {
  fakeFetch({
    'GET /plans/meal/active': NO_PLAN, 'GET /plans/proposals/pending': NO_PENDING,
    'POST /plans/meal/generate': { status: 503, body: { detail: 'The coach is busy right now. Please try again in a minute.' } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Generate my plan' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The coach is busy right now')
  expect(await screen.findByRole('button', { name: 'Generate my plan' })).toBeEnabled()
})
