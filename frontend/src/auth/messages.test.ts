import { expect, test } from 'vitest'

import { friendlyAuthError } from './messages'

test.each([
  [{ code: 'invalid_credentials' }, 'Email or password is incorrect.'],
  [{ message: 'Invalid login credentials' }, 'Email or password is incorrect.'],
  [{ code: 'user_already_exists' }, 'An account with this email already exists. Try signing in instead.'],
  [{ code: 'weak_password' }, 'Please choose a stronger password (at least 8 characters).'],
  [{ status: 429 }, 'Too many attempts. Please wait a minute and try again.'],
  [{ message: 'something unexpected' }, 'Something went wrong. Please check your connection and try again.'],
])('%o -> %s', (error, expected) => {
  expect(friendlyAuthError(error)).toBe(expected)
})
