import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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
  meta: { specialists: [{ name: 'nutrition', status: 'ok', steps: 2, tokens: 1234, tools: ['search_foods', 'search_foods', 'get_food'] }], composed: false },
  ...over,
})

const type = (text: string) => fireEvent.change(screen.getByLabelText('Your message'), { target: { value: text } })
const send = () => fireEvent.click(screen.getByRole('button', { name: 'Send' }))

test('a message shows the reply, and "How this answer was made" lists what ran', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: reply() } })
  render()
  expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()                      // nothing typed yet
  type('  How much protein is in paneer?  ')
  send()
  expect(await screen.findByText('Paneer has about 18 g of protein per 100 g.')).toBeInTheDocument()
  expect(screen.getByText('How much protein is in paneer?')).toBeInTheDocument()            // the user's own line, trimmed
  expect(calls[0].body).toEqual({ message: 'How much protein is in paneer?' })              // a new chat sends no conversation id
  expect(screen.getByLabelText('Your message')).toHaveValue('')
  fireEvent.click(screen.getByText('How this answer was made'))
  expect(screen.getByText(/nutrition: answered in 2 steps, 1,234 tokens, used search_foods, get_food/)).toBeInTheDocument()
})

test('the second message continues the same conversation', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: reply() } })
  render()
  type('first')
  send()
  await screen.findByText(/18 g of protein/)
  type('second')
  send()
  await waitFor(() => expect(calls).toHaveLength(2))
  expect(calls[1].body).toEqual({ message: 'second', conversation_id: 'c1' })
})

test('Enter sends and Shift+Enter does not', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: reply() } })
  render()
  type('hello')
  fireEvent.keyDown(screen.getByLabelText('Your message'), { key: 'Enter', shiftKey: true })
  expect(calls).toHaveLength(0)
  fireEvent.keyDown(screen.getByLabelText('Your message'), { key: 'Enter' })
  await screen.findByText(/18 g of protein/)
  expect(calls).toHaveLength(1)
})

test('a message a guard stopped is shown as a notice, with no "how it was made" line', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ reply: 'I am really sorry you are feeling this way.', blocked: 'crisis', meta: { specialists: [], composed: false } }) } })
  render()
  type('something hard')
  send()
  const notice = await screen.findByText('I am really sorry you are feeling this way.')
  expect(notice.className).toContain('bg-warn-soft')
  expect(screen.queryByText('How this answer was made')).not.toBeInTheDocument()
})

test('a proposal shows a card; Approve answers it through the chat and shows the outcome', async () => {
  const calls = fakeFetch({
    'POST /chat': { body: reply({ reply: 'Proposal ready.', waiting_for: { kind: 'approve_proposal', proposal_id: 'p1', summary: 'A new 7-day meal plan' } }) },
    'POST /chat/c1/decide': { body: reply({ reply: 'Done. I saved that change.', waiting_for: null, meta: { specialists: [] } }) },
  })
  render()
  type('make me a plan')
  send()
  const card = await screen.findByRole('region', { name: 'Proposal waiting for your answer' })
  expect(within(card).getByText('A new 7-day meal plan')).toBeInTheDocument()
  expect(calls.filter((c) => c.path.endsWith('/decide'))).toHaveLength(0)                    // nothing is applied without the click
  fireEvent.click(within(card).getByRole('button', { name: 'Approve' }))
  expect(await screen.findByText('Done. I saved that change.')).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/chat/c1/decide')!.body).toEqual({ choice: 'approve' })   // only the choice: the server knows the proposal
  expect(screen.queryByRole('region', { name: 'Proposal waiting for your answer' })).not.toBeInTheDocument()
})

test('Reject sends reject', async () => {
  const calls = fakeFetch({
    'POST /chat': { body: reply({ waiting_for: { kind: 'approve_proposal', proposal_id: 'p1', summary: 'A plan' } }) },
    'POST /chat/c1/decide': { body: reply({ reply: 'No problem. I did not change anything.' }) },
  })
  render()
  type('plan')
  send()
  fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
  expect(await screen.findByText('No problem. I did not change anything.')).toBeInTheDocument()
  expect(calls.find((c) => c.path.endsWith('/decide'))!.body).toEqual({ choice: 'reject' })
})

test('sending a new message while a card is waiting removes the card (it belongs to the latest turn)', async () => {
  fakeFetch({
    'POST /chat': { body: reply({ waiting_for: { kind: 'approve_proposal', proposal_id: 'p1', summary: 'A plan' } }) },
  })
  render()
  type('plan')
  send()
  await screen.findByRole('region', { name: 'Proposal waiting for your answer' })
  fakeFetch({ 'POST /chat': { body: reply({ reply: 'Sure.', waiting_for: null }) } })
  type('never mind')
  send()
  await screen.findByText('Sure.')
  expect(screen.queryByRole('region', { name: 'Proposal waiting for your answer' })).not.toBeInTheDocument()
})

test('a rate limit shows the server message, keeps what you typed and takes the unsent message off the screen', async () => {
  fakeFetch({ 'POST /chat': { status: 429, body: { detail: 'You are sending messages very quickly. Please wait about 40 seconds and try again.', request_id: 'r-9' } } })
  render()
  type('one too many')
  send()
  expect(await screen.findByRole('alert')).toHaveTextContent('Please wait about 40 seconds')
  expect(screen.getByLabelText('Your message')).toHaveValue('one too many')
  expect(within(screen.getByRole('region', { name: 'Conversation' })).queryByText('one too many')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled()                           // they can try again
})

test('a busy model (503) shows the readable message the server sent', async () => {
  fakeFetch({ 'POST /chat': { status: 503, body: { detail: 'The coach is very busy right now. Please try again in a minute.' } } })
  render()
  type('hello')
  send()
  expect(await screen.findByRole('alert')).toHaveTextContent('very busy')
})

test('answering a card that is no longer waiting (409) shows the message and removes the card', async () => {
  fakeFetch({
    'POST /chat': { body: reply({ waiting_for: { kind: 'approve_proposal', proposal_id: 'p1', summary: 'A plan' } }) },
    'POST /chat/c1/decide': { status: 409, body: { detail: 'Nothing is waiting for your answer in this chat.' } },
  })
  render()
  type('plan')
  send()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Nothing is waiting')
  expect(screen.queryByRole('region', { name: 'Proposal waiting for your answer' })).not.toBeInTheDocument()
})

test('New chat clears the screen and the next message starts a new conversation', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: reply() } })
  render()
  expect(screen.getByRole('button', { name: 'New chat' })).toBeDisabled()                     // nothing to clear yet
  type('first')
  send()
  await screen.findByText(/18 g of protein/)
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
  expect(screen.queryByText(/18 g of protein/)).not.toBeInTheDocument()
  type('fresh start')
  send()
  await waitFor(() => expect(calls).toHaveLength(2))
  expect(calls[1].body).toEqual({ message: 'fresh start' })                                   // no conversation id
})

test('the message box allows at most 1000 characters, like the server', () => {
  fakeFetch({})
  render()
  expect(screen.getByLabelText('Your message')).toHaveAttribute('maxlength', '1000')
})
