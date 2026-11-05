import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'
import { OnboardingPage } from './OnboardingPage'
import { PRIVACY_NOTICE_VERSION } from './privacyNotice'

afterEach(() => vi.unstubAllGlobals())

const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/onboarding': <OnboardingPage />, '/': <p>home</p> }, '/onboarding')

test('a new user sees the privacy note first, and must tick the box', async () => {
  fakeFetch({ 'GET /onboarding/status': { body: status('consent') } })
  render()

  expect(await screen.findByRole('heading', { name: 'Before we start' })).toBeInTheDocument()
  expect(screen.getByText('Step 1 of 6')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Agree and continue' })).toBeDisabled()
})

test('agreeing saves consent with the notice version, then shows the basics form', async () => {
  const calls = fakeFetch({
    'GET /onboarding/status': { body: status('consent') },
    'PUT /onboarding/consent': { body: status('basics', ['consent']) },
  })
  render()

  fireEvent.click(await screen.findByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'Agree and continue' }))

  expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument()
  expect(screen.getByText('Step 2 of 6')).toBeInTheDocument()
  const consent = calls.find((c) => c.path === '/onboarding/consent')!
  expect(consent.body).toEqual({ health_data_consent: true, privacy_notice_version: PRIVACY_NOTICE_VERSION })
  expect(consent.headers.Authorization).toBe('Bearer tok')
})

function fillBasics() {
  fireEvent.change(screen.getByLabelText('Date of birth'), { target: { value: '1995-08-20' } })
  fireEvent.click(screen.getByLabelText('Female'))
  fireEvent.change(screen.getByLabelText('Height (cm)'), { target: { value: '162.5' } })
  fireEvent.change(screen.getByLabelText('Weight (kg)'), { target: { value: '58' } })
  fireEvent.click(screen.getByLabelText(/Lightly active/))
}

test('basics are sent as numbers and the next step appears', async () => {
  const calls = fakeFetch({
    'GET /onboarding/status': { body: status('basics', ['consent']) },
    'PUT /onboarding/basics': { body: status('goal', ['consent', 'basics']) },
  })
  render()
  await screen.findByRole('heading', { name: 'About you' })
  fillBasics()
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

  expect(await screen.findByText('Step 3 of 6')).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/onboarding/basics')!.body).toEqual({
    display_name: null, date_of_birth: '1995-08-20', sex: 'female',
    height_cm: 162.5, weight_kg: 58, activity_level: 'light',
  })
})

test("the backend's field errors are shown next to the right fields", async () => {
  fakeFetch({
    'GET /onboarding/status': { body: status('basics', ['consent']) },
    'PUT /onboarding/basics': {
      status: 422,
      body: {
        detail: 'Please check the highlighted fields.',
        errors: [{ field: 'date_of_birth', message: 'you must be at least 18 to use this app' }],
        request_id: 'req-9',
      },
    },
  })
  render()
  await screen.findByRole('heading', { name: 'About you' })
  fillBasics()
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

  expect(await screen.findByText('you must be at least 18 to use this app')).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('Please check the highlighted fields.')
  expect(screen.getByRole('alert')).toHaveTextContent('Reference: req-9')
})

test('finished users are sent home', async () => {
  fakeFetch({ 'GET /onboarding/status': { body: status('done', [], true) } })
  render()
  await waitFor(() => expect(screen.getByText('home')).toBeInTheDocument())
})

test('a server that cannot be reached shows a clear message', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
  render()
  expect(await screen.findByRole('alert')).toHaveTextContent("Can't reach the server")
})
