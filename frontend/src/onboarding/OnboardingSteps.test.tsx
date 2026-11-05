import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'
import { OnboardingPage } from './OnboardingPage'

afterEach(() => vi.unstubAllGlobals())

const render = () =>
  renderWithAuth(fakeAuth({ session: fakeSession() }), { '/onboarding': <OnboardingPage />, '/': <p>home</p> }, '/onboarding')

const sent = (calls: { path: string; body: unknown }[], path: string) => calls.find((c) => c.path === path)!.body

// "Lose fat" exactly, not "Lose fat and build muscle".
const loseFat = () => screen.findByRole('radio', { name: /^Lose fat(?! and)/ })

// --- Goal ---

test('goal: sends the chosen goal and target weight', async () => {
  const calls = fakeFetch({
    'GET /onboarding/status': { body: status('goal', ['consent', 'basics']) },
    'PUT /onboarding/goal': { body: status('preferences', ['consent', 'basics', 'goal']) },
  })
  render()
  fireEvent.click(await loseFat())
  fireEvent.change(screen.getByLabelText(/Target weight/), { target: { value: '54' } })
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

  expect(await screen.findByRole('heading', { name: 'Food preferences' })).toBeInTheDocument()
  expect(sent(calls, '/onboarding/goal')).toEqual({ goal_type: 'fat_loss', target_weight_kg: 54 })
})

test("goal: shows the backend's target-weight message", async () => {
  fakeFetch({
    'GET /onboarding/status': { body: status('goal', ['consent', 'basics']) },
    'PUT /onboarding/goal': {
      status: 422,
      body: { detail: 'For fat loss, the target weight should be below your current weight.', request_id: 'r1' },
    },
  })
  render()
  fireEvent.click(await loseFat())
  fireEvent.change(screen.getByLabelText(/Target weight/), { target: { value: '70' } })
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('should be below your current weight')
})

// --- Preferences ---

test('preferences: diet plus disliked foods (Enter adds, repeats ignored, × removes)', async () => {
  const calls = fakeFetch({
    'GET /onboarding/status': { body: status('preferences', ['consent', 'basics', 'goal']) },
    'PUT /onboarding/preferences': { body: status('training', ['consent', 'basics', 'goal', 'preferences']) },
  })
  render()
  fireEvent.click(await screen.findByLabelText(/^Vegetarian/))
  const input = screen.getByLabelText("Foods you don't like (optional)")
  for (const food of ['Karela', 'karela', 'Baingan', 'Methi']) {
    fireEvent.change(input, { target: { value: food } })
    fireEvent.keyDown(input, { key: 'Enter' })
  }
  fireEvent.click(screen.getByRole('button', { name: 'Remove Methi' }))
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

  await screen.findByRole('heading', { name: 'Your training' })
  expect(sent(calls, '/onboarding/preferences')).toEqual({ diet_type: 'vegetarian', disliked_foods: ['Karela', 'Baingan'] })
})

// --- Training ---

test('training: experience, location, equipment and days', async () => {
  const calls = fakeFetch({
    'GET /onboarding/status': { body: status('training', ['consent', 'basics', 'goal', 'preferences']) },
    'PUT /onboarding/training': { body: status('screening', ['consent', 'basics', 'goal', 'preferences', 'training']) },
  })
  render()
  fireEvent.click(await screen.findByLabelText(/^Beginner/))
  fireEvent.click(screen.getByLabelText('Home'))
  fireEvent.click(screen.getByLabelText('Dumbbells'))
  fireEvent.click(screen.getByLabelText('Yoga mat'))
  fireEvent.click(screen.getByLabelText('Dumbbells')) // untick again
  const continueButton = screen.getByRole('button', { name: 'Continue' })
  expect(continueButton).toBeDisabled() // days not chosen yet
  fireEvent.click(screen.getByRole('button', { name: '3' }))
  fireEvent.click(continueButton)

  await screen.findByRole('heading', { name: 'Health check' })
  expect(sent(calls, '/onboarding/training')).toEqual({
    experience_level: 'beginner', workout_location: 'home', equipment: ['yoga_mat'], days_per_week: 3,
  })
})

// --- Screening ---

test('screening: Continue stays disabled until all six questions are answered', async () => {
  const calls = fakeFetch({
    'GET /onboarding/status': { body: status('screening', ['consent', 'basics', 'goal', 'preferences', 'training']) },
    'PUT /onboarding/screening': { body: status('complete', ['consent', 'basics', 'goal', 'preferences', 'training', 'screening']) },
  })
  render()
  await screen.findByRole('heading', { name: 'Health check' })
  const continueButton = screen.getByRole('button', { name: 'Continue' })

  const questions = screen.getAllByRole('group').slice(0, 6) // the six Yes/No questions, in order
  questions.forEach((question, i) => {
    expect(continueButton).toBeDisabled()
    const answer = i === 3 ? 'Yes' : 'No' // question 4 is "kidney disease?"
    fireEvent.click(within(question).getByLabelText(answer))
  })
  fireEvent.click(screen.getByLabelText('Knee'))
  expect(continueButton).toBeEnabled()
  fireEvent.click(continueButton)

  await screen.findByRole('heading', { name: 'All set' })
  expect(sent(calls, '/onboarding/screening')).toEqual({
    pregnant_or_breastfeeding: false, diabetes: false, heart_or_bp: false, kidney: true,
    recent_surgery_or_injury: false, eating_disorder_history: false, injury_areas: ['knee'],
  })
})

// --- Finish ---

test('finish: calculates the targets and goes home', async () => {
  const calls = fakeFetch({
    'GET /onboarding/status': { body: status('complete', ['consent', 'basics', 'goal', 'preferences', 'training', 'screening']) },
    'POST /onboarding/complete': { body: { calorie_target_kcal: 1600 } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Calculate my targets' }))

  await waitFor(() => expect(screen.getByText('home')).toBeInTheDocument())
  expect(calls.some((c) => c.method === 'POST' && c.path === '/onboarding/complete')).toBe(true)
})
