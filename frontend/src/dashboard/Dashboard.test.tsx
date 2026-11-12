import { screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from '../App'
import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'
import type { Today } from './types'

afterEach(() => vi.unstubAllGlobals())

const TARGETS = {
  calorie_target_kcal: 1408, protein_g: 116, fat_g: 39, carbs_g: 148, protein_pct: 33, carbs_pct: 42, fat_pct: 25,
  reasons: [], doctor_note: null, focus_on_habits: false,
}
const FORECAST = { status: 'no_target', message: 'Set a target weight to see a goal date.', current_weight_kg: null, target_weight_kg: null,
  weekly_change_kg: null, earliest: null, likely: null, latest: null, weeks_likely: null, note: null }

const TODAY: Today = {
  date: '2026-11-11', weekday: 'Wednesday', numbers_hidden: false,
  progress: {
    kcal: { eaten: 704, target: 1408, percent: 50 }, protein_g: { eaten: 29, target: 116, percent: 25 },
    carbs_g: { eaten: 148, target: 148, percent: 100 }, fat_g: { eaten: 59, target: 39, percent: 151 },
  },
  logged: [{ slot: 'lunch', foods: ['Roti / chapati (no fat) (2 piece)', 'Sambar (1 katori)'] }],
  meal_plan: { kcal: 1400, meals: [
    { slot: 'breakfast', items: [{ name: 'Idli', text: '4 pieces (160 g)', kcal: 232 }] },
    { slot: 'lunch', items: [{ name: 'Khichdi', text: '1 katori (150 g)', kcal: 200 }, { name: 'Curd', text: '1 cup (200 g)', kcal: 120 }] },
  ] },
  workout: { rest_day: false, focus: 'Full body A', minutes: 25, exercises: [{ name: 'Bodyweight Squat', sets: 2, reps: '8-12' }, { name: 'Glute Bridge', sets: 2, reps: '8-12' }] },
}

const signedIn = () => fakeAuth({ session: fakeSession('kruthi@example.test') })
function home(today: unknown, forecast: unknown = FORECAST, targets: unknown = TARGETS) {
  return fakeFetch({
    'GET /onboarding/status': { body: status('done', [], true) },
    'GET /targets/current': { body: targets },
    'GET /targets/forecast': { body: forecast },
    'GET /dashboard/today': today as never,
  })
}
const render = () => renderWithAuth(signedIn(), { '*': <App /> }, '/')

test('Home shows today: a bar for each of calories, protein, carbs and fat with the percentage the server calculated', async () => {
  home({ body: TODAY })
  render()
  const progress = await screen.findByRole('region', { name: "Today's progress" })
  expect(within(progress).getByText('Today, Wednesday')).toBeInTheDocument()
  const calories = within(progress).getByRole('progressbar', { name: 'Calories eaten today' })
  expect(calories).toHaveAttribute('aria-valuenow', '50')
  expect(within(progress).getByText('704 / 1408 kcal')).toBeInTheDocument()
  expect(within(progress).getByRole('progressbar', { name: 'Protein eaten today' })).toHaveAttribute('aria-valuenow', '25')
  expect(progress).toHaveTextContent('29 / 116 g')                                              // protein card (the number is split over two elements)
})

test('going over a target fills the bar completely, says so in words and changes its colour', async () => {
  home({ body: TODAY })
  render()
  const fat = await screen.findByRole('progressbar', { name: 'Fat eaten today' })
  expect(fat).toHaveAttribute('aria-valuenow', '100')                                          // the bar never overflows
  expect(fat).toHaveAttribute('aria-valuetext', '151% of your fat target')
  expect((fat.firstElementChild as HTMLElement).className).toContain('bg-warn')
  const ring = await screen.findByRole('progressbar', { name: 'Calories eaten today' })
  expect(ring).toHaveAttribute('data-state', 'under')                                           // the calorie ring (50%) is still lime
})

test('what was logged today is listed by meal', async () => {
  home({ body: TODAY })
  render()
  const logged = await screen.findByRole('list', { name: 'Logged today' })
  expect(logged).toHaveTextContent('lunch: Roti / chapati (no fat) (2 piece), Sambar (1 katori)')
})

test("today's planned meals and workout come from the approved plans", async () => {
  home({ body: TODAY })
  render()
  const meals = await screen.findByRole('region', { name: "Today's meals" })
  expect(meals).toHaveTextContent('breakfast: Idli (4 pieces (160 g))')
  expect(meals).toHaveTextContent('lunch: Khichdi (1 katori (150 g)), Curd (1 cup (200 g))')
  expect(within(meals).getByText('Planned: about 1400 kcal.')).toBeInTheDocument()
  expect(within(meals).getByRole('link', { name: 'Log a meal' })).toHaveAttribute('href', '/log')
  const workout = screen.getByRole('region', { name: "Today's workout" })
  expect(workout).toHaveTextContent('Full body A, about 25 minutes')
  expect(workout).toHaveTextContent('Bodyweight Squat: 2 sets of 8-12')
})

test('a rest day says so', async () => {
  home({ body: { ...TODAY, workout: { rest_day: true, focus: null, minutes: null, exercises: [] } } })
  render()
  expect(await screen.findByText(/Rest day\. Recovery is part of the plan/)).toBeInTheDocument()
})

test('with no plans yet the cards point to where to make them, and an empty day says nothing is logged', async () => {
  home({ body: { ...TODAY, logged: [], meal_plan: null, workout: null } })
  render()
  expect(await screen.findByText('Nothing logged today yet.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Make your meal plan' })).toHaveAttribute('href', '/meal-plan')
  expect(screen.getByRole('link', { name: 'Make your workout plan' })).toHaveAttribute('href', '/workout')
})

test('a user who must not see numbers gets no bars, no calories and no planned kcal', async () => {
  const hidden: Today = { ...TODAY, numbers_hidden: true, progress: null, meal_plan: { kcal: null, meals: [{ slot: 'lunch', items: [{ name: 'Khichdi', text: '1 katori (150 g)', kcal: null }] }] } }
  home({ body: hidden }, { ...FORECAST, status: 'habits_only' }, { ...TARGETS, focus_on_habits: true, calorie_target_kcal: null, protein_g: null, fat_g: null, carbs_g: null, protein_pct: null, carbs_pct: null, fat_pct: null })
  render()
  const progress = await screen.findByRole('region', { name: "Today's progress" })
  expect(within(progress).queryByRole('progressbar')).not.toBeInTheDocument()
  expect(progress).toHaveTextContent('no numbers to track')
  expect(screen.getByRole('region', { name: "Today's meals" })).not.toHaveTextContent(/kcal/)
})

test('if the summary cannot load, the targets still show and no error is thrown at the person', async () => {
  home({ status: 500, body: { detail: 'Something went wrong on our side. Please try again.' } })
  render()
  expect(await screen.findByText('1,408')).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: "Today's progress" })).not.toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('the dashboard sits on Home above the targets and keeps the quick links', async () => {
  home({ body: TODAY })
  render()
  await screen.findByRole('region', { name: "Today's progress" })
  expect(screen.getByRole('link', { name: 'Meal plan' })).toHaveAttribute('href', '/meal-plan')
  expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings')
  expect(screen.getByText('1,408')).toBeInTheDocument()
})
