import { afterEach, expect, test, vi } from 'vitest'

import { fakeFetch } from '../test/fakeFetch'
import { ApiError, UNREACHABLE, createApi } from './api'

afterEach(() => vi.unstubAllGlobals())

// Await a call that should fail, and return its ApiError (fails the test otherwise).
async function failure(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.then(() => null, (e: unknown) => e)
  expect(error).toBeInstanceOf(ApiError)
  return error as ApiError
}

test('sends the login token and JSON body', async () => {
  const calls = fakeFetch({ 'PUT /onboarding/consent': { body: { ok: true } } })
  const result = await createApi('token-abc').put('/onboarding/consent', { a: 1 })

  expect(result).toEqual({ ok: true })
  expect(calls[0].headers.Authorization).toBe('Bearer token-abc')
  expect(calls[0].headers['Content-Type']).toBe('application/json')
  expect(calls[0].body).toEqual({ a: 1 })
})

test('no token means no Authorization header', async () => {
  const calls = fakeFetch({ 'GET /health': { body: { status: 'ok' } } })
  await createApi(null).get('/health')
  expect(calls[0].headers.Authorization).toBeUndefined()
})

test('turns our error format into an ApiError with field messages', async () => {
  fakeFetch({
    'PUT /onboarding/basics': {
      status: 422,
      body: {
        detail: 'Please check the highlighted fields.',
        errors: [{ field: 'height_cm', message: 'Input should be greater than or equal to 120' }],
        request_id: 'req-42',
      },
    },
  })
  const error = await failure(createApi('t').put('/onboarding/basics', {}))

  expect(error.status).toBe(422)
  expect(error.message).toBe('Please check the highlighted fields.')
  expect(error.fieldErrors).toEqual({ height_cm: 'Input should be greater than or equal to 120' })
  expect(error.requestId).toBe('req-42')
})

test('a server that cannot be reached gives a plain message', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
  const error = await failure(createApi('t').get('/onboarding/status'))

  expect(error.status).toBe(0)
  expect(error.message).toBe(UNREACHABLE)
})
