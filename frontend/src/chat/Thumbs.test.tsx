import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch } from '../test/fakeFetch'
import { ChatPage } from './ChatPage'
import type { ChatReply } from './types'

afterEach(() => vi.unstubAllGlobals())

const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/chat': <ChatPage />, '/': <p>home</p> }, '/chat')
const reply = (over: Partial<ChatReply> = {}): ChatReply => ({
  conversation_id: 'c1', reply: 'Paneer has about 18 g of protein per 100 g.', blocked: null, waiting_for: null, decisions: [],
  meta: { specialists: [], composed: false }, message_id: 7, ...over,
})
const ask = async () => {
  fireEvent.change(screen.getByLabelText('Your message'), { target: { value: 'protein in paneer' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await screen.findByText(/18 g of protein/)
}

test('a coach answer has thumbs; a tap saves the choice, and tapping it again takes it back', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: reply() }, 'PUT /chat/messages/7/feedback': { status: 204, body: null } })
  render()
  await ask()
  const down = screen.getByRole('button', { name: 'Not helpful' })
  fireEvent.click(down)
  await waitFor(() => expect(calls.find((c) => c.method === 'PUT')!.body).toEqual({ value: 'down' }))
  expect(down).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(down)
  await waitFor(() => expect(calls.filter((c) => c.method === 'PUT')[1].body).toEqual({ value: null }))
  expect(down).toHaveAttribute('aria-pressed', 'false')
})

test('if saving the thumb fails it goes back and the error is shown', async () => {
  fakeFetch({ 'POST /chat': { body: reply() }, 'PUT /chat/messages/7/feedback': { status: 500, body: { detail: 'Something went wrong on our side.' } } })
  render()
  await ask()
  const up = screen.getByRole('button', { name: 'Helpful answer' })
  fireEvent.click(up)
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  expect(up).toHaveAttribute('aria-pressed', 'false')
})

test('a notice from a guard gets no thumbs', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ blocked: 'crisis', reply: 'Please reach out for help.' }) } })
  render()
  fireEvent.change(screen.getByLabelText('Your message'), { target: { value: 'hi' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await screen.findByText('Please reach out for help.')
  expect(screen.queryByRole('group', { name: 'Rate this answer' })).not.toBeInTheDocument()
})

test('an old chat shows the thumbs that were saved', async () => {
  sessionStorage.setItem('coach-chat-id', 'c9')
  fakeFetch({ 'GET /chat/c9': { body: { id: 'c9', messages: [
    { id: 1, role: 'user', content: 'hi', blocked: null, feedback: null },
    { id: 2, role: 'assistant', content: 'Hello!', blocked: null, feedback: 'up' }] } } })
  render()
  await screen.findByText('Hello!')
  expect(screen.getByRole('button', { name: 'Helpful answer' })).toHaveAttribute('aria-pressed', 'true')
})
