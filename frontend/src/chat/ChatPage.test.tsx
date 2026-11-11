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
  expect(notice.closest('[data-bubble]')).toHaveAttribute('data-bubble', 'notice')
  expect(notice.closest('[data-bubble]')!.className).toContain('bg-warn-soft')
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

// ---------- past chats and keeping the open chat (7.11h) ----------

const SAVED = { id: 'c9', messages: [
  { id: 1, role: 'user', content: 'tell me about paneer', blocked: null },
  { id: 2, role: 'assistant', content: 'Paneer is a dairy food.', blocked: null },
  { id: 3, role: 'user', content: 'something hard', blocked: 'crisis' },
  { id: 4, role: 'assistant', content: 'I am really sorry you feel this way.', blocked: 'crisis' },
] }
const LIST = { conversations: [{ id: 'c9', title: 'tell me about paneer', updated_at: '2026-11-10T10:00:00Z' }, { id: 'c8', title: 'calories in rotis', updated_at: '2026-11-09T09:00:00Z' }] }

test('Past chats lists earlier chats; opening one shows its messages and the next message continues it', async () => {
  const calls = fakeFetch({ 'GET /chat': { body: LIST }, 'GET /chat/c9': { body: SAVED }, 'POST /chat': { body: reply({ conversation_id: 'c9' }) } })
  render()
  fireEvent.click(screen.getByRole('button', { name: 'Past chats' }))
  const list = await screen.findByRole('region', { name: 'Past chats' })
  expect(within(list).getByText('calories in rotis')).toBeInTheDocument()
  fireEvent.click(within(list).getByText('tell me about paneer'))
  expect(await screen.findByText('Paneer is a dairy food.')).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Past chats' })).not.toBeInTheDocument()            // the list closes once a chat is open
  expect(screen.getByText('I am really sorry you feel this way.').closest('[data-bubble]')).toHaveAttribute('data-bubble', 'notice')   // a stopped turn still looks like a notice
  type('and the fat?')
  send()
  await waitFor(() => expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1))
  expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ message: 'and the fat?', conversation_id: 'c9' })
})

test('deleting a past chat removes it from the list; deleting the open chat clears the screen', async () => {
  const calls = fakeFetch({ 'GET /chat': { body: LIST }, 'GET /chat/c9': { body: SAVED }, 'DELETE /chat/c9': { status: 204, body: null }, 'DELETE /chat/c8': { status: 204, body: null } })
  render()
  fireEvent.click(screen.getByRole('button', { name: 'Past chats' }))
  const list = await screen.findByRole('region', { name: 'Past chats' })
  fireEvent.click(within(list).getByRole('button', { name: 'Delete chat: calories in rotis' }))
  await waitFor(() => expect(within(list).queryByText('calories in rotis')).not.toBeInTheDocument())
  expect(calls.some((c) => c.method === 'DELETE' && c.path === '/chat/c8')).toBe(true)
  fireEvent.click(within(list).getByText('tell me about paneer'))                                  // open the other one...
  await screen.findByText('Paneer is a dairy food.')
  fireEvent.click(screen.getByRole('button', { name: 'Past chats' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Delete chat: tell me about paneer' }))   // ...then delete it while open
  await waitFor(() => expect(screen.queryByText('Paneer is a dairy food.')).not.toBeInTheDocument())
})

test('a failed delete shows a message and keeps the chat in the list', async () => {
  fakeFetch({ 'GET /chat': { body: LIST }, 'DELETE /chat/c8': { status: 404, body: { detail: "We couldn't find that conversation." } } })
  render()
  fireEvent.click(screen.getByRole('button', { name: 'Past chats' }))
  const list = await screen.findByRole('region', { name: 'Past chats' })
  fireEvent.click(within(list).getByRole('button', { name: 'Delete chat: calories in rotis' }))
  expect(await within(list).findByRole('alert')).toHaveTextContent("couldn't find that conversation")
  expect(within(list).getByText('calories in rotis')).toBeInTheDocument()
})

test('an empty list says there are no earlier chats yet', async () => {
  fakeFetch({ 'GET /chat': { body: { conversations: [] } } })
  render()
  fireEvent.click(screen.getByRole('button', { name: 'Past chats' }))
  expect(await screen.findByText('No earlier chats yet.')).toBeInTheDocument()
})

test('a refresh brings the open chat back (the id is remembered for the tab)', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ conversation_id: 'c9' }) } })
  const first = render()
  type('hello')
  send()
  await screen.findByText(/18 g of protein/)
  expect(sessionStorage.getItem('coach-chat-id')).toBe('c9')
  first.unmount()                                                                                 // "refresh": a brand-new page
  fakeFetch({ 'GET /chat/c9': { body: SAVED } })
  render()
  expect(await screen.findByText('Paneer is a dairy food.')).toBeInTheDocument()
})

test('a remembered chat that no longer exists is forgotten quietly, with no error shown', async () => {
  sessionStorage.setItem('coach-chat-id', 'gone')
  fakeFetch({ 'GET /chat/gone': { status: 404, body: { detail: "We couldn't find that conversation." } } })
  render()
  await waitFor(() => expect(sessionStorage.getItem('coach-chat-id')).toBeNull())
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()                              // a normal empty chat
})

test('New chat forgets the remembered chat', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ conversation_id: 'c9' }) } })
  render()
  type('hello')
  send()
  await screen.findByText(/18 g of protein/)
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
  expect(sessionStorage.getItem('coach-chat-id')).toBeNull()
})

// ---------- example questions (chips) ----------

test('an empty chat offers example questions; tapping one sends it at once and the chips go away', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: reply() } })
  render()
  const chips = screen.getByRole('list', { name: 'Example questions' })
  expect(within(chips).getAllByRole('button').length).toBeGreaterThanOrEqual(6)
  fireEvent.click(within(chips).getByRole('button', { name: 'Protein in paneer' }))
  expect(await screen.findByText(/18 g of protein/)).toBeInTheDocument()
  expect(calls[0].body).toEqual({ message: 'How much protein is in paneer?' })              // sent exactly as the chip's full question
  expect(screen.queryByRole('list', { name: 'Example questions' })).not.toBeInTheDocument()    // they leave once the conversation starts
})

test('every example question is a real message within the limit, and they cover each chat skill', async () => {
  const { SUGGESTIONS } = await import('./suggestions')
  expect(new Set(SUGGESTIONS.map((s) => s.label)).size).toBe(SUGGESTIONS.length)
  for (const s of SUGGESTIONS) {
    expect(s.message.length).toBeGreaterThan(5)
    expect(s.message.length).toBeLessThanOrEqual(1000)
  }
  const text = SUGGESTIONS.map((s) => s.message.toLowerCase()).join(' | ')
  for (const skill of ['protein is in', 'high in protein', 'workout', 'lunch', 'on track', 'plank', 'i ate']) expect(text).toContain(skill)
})

test('the example chips come back after New chat', async () => {
  fakeFetch({ 'POST /chat': { body: reply() } })
  render()
  fireEvent.click(screen.getByRole('button', { name: 'Log a meal' }))
  await screen.findByText(/18 g of protein/)
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
  expect(screen.getByRole('list', { name: 'Example questions' })).toBeInTheDocument()
})

test('the chips are not offered when an earlier chat is reopened', async () => {
  sessionStorage.setItem('coach-chat-id', 'c9')
  fakeFetch({ 'GET /chat/c9': { body: { id: 'c9', messages: [{ id: 1, role: 'user', content: 'hi', blocked: null }, { id: 2, role: 'assistant', content: 'Hello!', blocked: null }] } } })
  render()
  expect(await screen.findByText('Hello!')).toBeInTheDocument()
  expect(screen.queryByRole('list', { name: 'Example questions' })).not.toBeInTheDocument()
})

// ---------- readable replies, honest waiting, and follow-up chips (audit follow-up) ----------

test('a reply with bullets, numbered steps and bold is shown as real lists and bold text, never as raw symbols', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ reply: 'Here is how:\n1. Stand tall\n2. Sit back\n\n* Keep your chest **up**\n* Heels flat' }) } })
  render()
  type('how do I squat')
  send()
  const bubble = (await screen.findByText('Here is how:')).closest('[data-bubble]') as HTMLElement
  expect(within(bubble).getAllByRole('list')).toHaveLength(2)
  expect(within(bubble).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Stand tall', 'Sit back', 'Keep your chest up', 'Heels flat'])
  expect(bubble.querySelector('strong')?.textContent).toBe('up')
  expect(bubble.textContent).not.toContain('*')
})

test('a reply that contains markup is shown as plain text, never run', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ reply: '<img src=x onerror=alert(1)> and <b>bold?</b>' }) } })
  const view = render()
  type('hi')
  send()
  const bubble = (await screen.findByText(/onerror/)).closest('[data-bubble]') as HTMLElement
  expect(bubble.querySelector('img')).toBeNull()
  expect(bubble.querySelector('b')).toBeNull()
  expect(bubble.textContent).toContain('<img src=x onerror=alert(1)>')
  view.unmount()
})

test('while the coach is working it counts the seconds, and after 10 it says the service can be slow', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  try {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))                              // never answers
    render()
    type('hello')
    send()
    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('The coach is thinking')
    expect(status).not.toHaveTextContent('Still working')
    await vi.advanceTimersByTimeAsync(11_000)
    expect(screen.getByRole('status')).toHaveTextContent(/1[01] s/)
    expect(screen.getByRole('status')).toHaveTextContent('Still working: the AI service can be slow at times.')
  } finally {
    vi.useRealTimers()
  }
})

test('after an answer the chips depend on who answered and never repeat a question already asked', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ meta: { specialists: [{ name: 'my_plan', status: 'ok', steps: 1, tokens: 10, tools: ['get_week_logged'] }], composed: false } }) } })
  render()
  type('Am I on track this week?')
  send()
  const chips = await screen.findByRole('list', { name: 'Suggested next questions' })
  const labels = within(chips).getAllByRole('button').map((b) => b.textContent)
  expect(labels).toEqual(['My weight progress', "Tomorrow's workout"])                          // "Am I on track?" was just asked, so it is not offered again
})

test('a follow-up chip sends its full question', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: reply() } })
  render()
  type('how much protein in paneer')
  send()
  await screen.findByRole('list', { name: 'Suggested next questions' })
  fireEvent.click(screen.getByRole('button', { name: 'High-protein foods' }))
  await waitFor(() => expect(calls.filter((c) => c.method === 'POST')).toHaveLength(2))
  expect(calls.filter((c) => c.method === 'POST')[1].body).toMatchObject({ message: 'Which vegetarian foods are high in protein?', conversation_id: 'c1' })
})

test('no chips while a proposal card waits for an answer, and the starting examples come back after a reply no specialist gave', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ waiting_for: { kind: 'approve_proposal', proposal_id: 'p1', summary: 'A plan' } }) } })
  render()
  type('plan')
  send()
  await screen.findByRole('region', { name: 'Proposal waiting for your answer' })
  expect(screen.queryByRole('list', { name: 'Suggested next questions' })).not.toBeInTheDocument()
})

test('after a reply with no specialist (a greeting) the first examples are offered again', async () => {
  fakeFetch({ 'POST /chat': { body: reply({ reply: 'Hi!', meta: { specialists: [], composed: false } }) } })
  render()
  type('hello')
  send()
  const chips = await screen.findByRole('list', { name: 'Suggested next questions' })
  expect(within(chips).getAllByRole('button')[0]).toHaveTextContent('Protein in paneer')
})
