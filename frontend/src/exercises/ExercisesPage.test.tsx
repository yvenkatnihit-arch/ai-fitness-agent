import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch } from '../test/fakeFetch'
import { ExercisesPage } from './ExercisesPage'
import type { Exercise, ExerciseList } from './types'

afterEach(() => vi.unstubAllGlobals())

const exercise = (over: Partial<Exercise>): Exercise => ({
  id: 1, key: 'plank', name: 'Plank', muscle_groups: ['abs'], equipment: [], location: 'both', difficulty: 'beginner',
  movement_pattern: 'core', form_cues: ['Body in a straight line', 'Breathe steadily'], verified: false, ...over,
})
const PLANK = exercise({})
const CURL = exercise({ id: 2, key: 'curl', name: 'Dumbbell Biceps Curl', muscle_groups: ['biceps'], equipment: ['dumbbells'],
  form_cues: ['Elbows stay at your sides', 'Lower slowly'] })
const LIST: ExerciseList = {
  setting: 'gym', level: 'beginner', injuries: ['knee', 'lower_back'], total_in_library: 102, shown: 2,
  exercises: [PLANK, CURL],
}
const HOME_LIST: ExerciseList = { ...LIST, setting: 'home', shown: 1, exercises: [PLANK] }

const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/exercises': <ExercisesPage />, '/': <p>home</p>, '/onboarding': <p>onboarding</p> }, '/exercises')

test('shows what is shown, what was left out and why, and the safety note', async () => {
  fakeFetch({ 'GET /exercises/for-me': { body: LIST } })
  render()
  expect(await screen.findByText(/Showing 2 of 102 exercises for the gym, beginner level/)).toBeInTheDocument()
  expect(screen.getByText(/Left out because of your knee, lower back/)).toBeInTheDocument()
  expect(screen.getByText(/safety tags on these exercises are still being reviewed/)).toBeInTheDocument()
  const cards = within(screen.getByRole('list', { name: 'Exercises' }))
  expect(cards.getByText('Plank')).toBeInTheDocument()
  expect(cards.getByText('No equipment', { exact: false })).toBeInTheDocument()
  expect(cards.getByText('Body in a straight line')).toBeInTheDocument()
})

test('muscle chips and the name search narrow the list without another request', async () => {
  const calls = fakeFetch({ 'GET /exercises/for-me': { body: LIST } })
  render()
  await screen.findByText('Plank')
  fireEvent.click(screen.getByRole('button', { name: 'biceps' }))
  expect(screen.queryByText('Plank')).not.toBeInTheDocument()
  expect(screen.getByText('Dumbbell Biceps Curl')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'all' }))
  fireEvent.change(screen.getByLabelText('Search exercises'), { target: { value: 'plan' } })
  expect(screen.getByText('Plank')).toBeInTheDocument()
  expect(screen.queryByText('Dumbbell Biceps Curl')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Search exercises'), { target: { value: 'zzz' } })
  expect(screen.getByText('No exercises match.')).toBeInTheDocument()
  expect(calls).toHaveLength(1)
})

test('switching to home asks the backend for the home list', async () => {
  const calls = fakeFetch({ 'GET /exercises/for-me': () => ({ body: calls.some((c) => c.query) ? HOME_LIST : LIST }) })
  render()
  await screen.findByText('Dumbbell Biceps Curl')
  expect(screen.getByRole('button', { name: 'gym' })).toHaveAttribute('aria-pressed', 'true')

  fireEvent.click(screen.getByRole('button', { name: 'home' }))
  await waitFor(() => expect(screen.queryByText('Dumbbell Biceps Curl')).not.toBeInTheDocument())
  expect(calls.at(-1)!.query).toBe('?setting=home')
  expect(screen.getByRole('button', { name: 'home' })).toHaveAttribute('aria-pressed', 'true')
})

test('unfinished onboarding shows the backend message and a way back', async () => {
  fakeFetch({ 'GET /exercises/for-me': { status: 409, body: { detail: 'Please finish the training and health steps of onboarding first.' } } })
  render()
  expect(await screen.findByText(/finish the training and health steps/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Go to onboarding' })).toBeInTheDocument()
})
