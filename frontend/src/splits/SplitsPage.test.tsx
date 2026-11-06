import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch } from '../test/fakeFetch'
import { SplitsPage } from './SplitsPage'
import type { Recommendation, SplitRecommendations } from './types'

afterEach(() => vi.unstubAllGlobals())

const UPPER_LOWER: Recommendation = {
  key: 'upper_lower_4', name: 'Upper / Lower', summary: 'Four sessions: upper body, lower body, then again.', fit: 'best',
  training_days: 4, recovery_days: 0, muscle_frequency: 2,
  reasons: ['4 training days a week, as you asked', 'Trains each muscle about 2 times a week'], cautions: [],
  schedule: [
    { label: 'Upper body', muscles: ['chest', 'back'], patterns: ['push_horizontal'] },
    { label: 'Lower body', muscles: ['quads', 'lower_back'], patterns: ['squat'] },
  ],
}
const FULL_BODY: Recommendation = {
  key: 'full_body_4', name: 'Full body', summary: 'Every session trains your whole body.', fit: 'possible',
  training_days: 4, recovery_days: 1, muscle_frequency: 4, reasons: ['Works for intermediate lifters'],
  cautions: ['Use the extra day for walking or stretching, not hard training'],
  schedule: [{ label: 'Full body A', muscles: ['quads'], patterns: ['squat'] }],
}
const DATA: SplitRecommendations = {
  days_per_week: 4, level: 'intermediate', goal: 'muscle_gain', chosen_key: null, recommendations: [UPPER_LOWER, FULL_BODY],
}

const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/splits': <SplitsPage />, '/': <p>home</p>, '/onboarding': <p>onboarding</p> }, '/splits')

test('shows your situation, the options best first, the reasons and the cautions', async () => {
  fakeFetch({ 'GET /splits/recommend': { body: DATA } })
  render()
  expect(await screen.findByText(/You train 4 days a week at intermediate level, aiming for muscle gain/)).toBeInTheDocument()
  const cards = within(screen.getByRole('list', { name: 'Splits' }))
  expect(cards.getAllByRole('heading').map((h) => h.textContent)).toEqual(['Upper / Lower', 'Full body'])
  expect(cards.getByText('Best match')).toBeInTheDocument()
  expect(cards.getByText('Possible')).toBeInTheDocument()
  expect(cards.getByText(/Trains each muscle about 2 times a week/)).toBeInTheDocument()
  expect(cards.getByText(/walking or stretching, not hard training/)).toBeInTheDocument()
  expect(cards.getByText('Day 1: Upper body')).toBeInTheDocument()
  expect(cards.getByText(/Plus 1 easy recovery day/)).toBeInTheDocument()
  expect(cards.getByText('quads, lower back')).toBeInTheDocument()   // underscores shown as spaces
})

test('choosing a split saves it and marks it as yours', async () => {
  const calls = fakeFetch({
    'GET /splits/recommend': { body: DATA },
    'PUT /splits/choice': { body: { split_key: 'upper_lower_4' } },
  })
  render()
  const buttons = await screen.findAllByRole('button', { name: 'Choose this split' })
  fireEvent.click(buttons[0])

  expect(await screen.findByRole('button', { name: '✓ Your split' })).toBeDisabled()
  expect(calls.find((c) => c.method === 'PUT')!.body).toEqual({ split_key: 'upper_lower_4' })
  expect(screen.getAllByRole('button', { name: 'Choose this split' })).toHaveLength(1)   // the other is still choosable
})

test('a split chosen earlier is shown as yours when the page opens', async () => {
  fakeFetch({ 'GET /splits/recommend': { body: { ...DATA, chosen_key: 'full_body_4' } } })
  render()
  expect(await screen.findByRole('button', { name: '✓ Your split' })).toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: 'Choose this split' })).toHaveLength(1)
})

test("a refused choice shows the backend's message and does not mark it as yours", async () => {
  fakeFetch({
    'GET /splits/recommend': { body: DATA },
    'PUT /splits/choice': { status: 422, body: { detail: 'Full body needs 4 training days a week, but you train 5.' } },
  })
  render()
  fireEvent.click((await screen.findAllByRole('button', { name: 'Choose this split' }))[1])
  expect(await screen.findByRole('alert')).toHaveTextContent('Full body needs 4 training days a week, but you train 5.')
  await waitFor(() => expect(screen.queryByRole('button', { name: '✓ Your split' })).not.toBeInTheDocument())
})

test('unfinished onboarding shows the message and a way back', async () => {
  fakeFetch({ 'GET /splits/recommend': { status: 409, body: { detail: 'Please finish the goal and training steps of onboarding first.' } } })
  render()
  expect(await screen.findByText(/finish the goal and training steps/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Go to onboarding' })).toBeInTheDocument()
})
