import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'

import App from '../App'
import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'
import { SUGGESTIONS } from './suggestions'

afterEach(() => vi.unstubAllGlobals())

const TARGETS = {
  calorie_target_kcal: 1408, protein_g: 116, fat_g: 39, carbs_g: 148, protein_pct: 33, carbs_pct: 42, fat_pct: 25,
  reasons: [], doctor_note: null, focus_on_habits: false,
}
const REPLY = {
  conversation_id: 'c1', reply: 'Paneer has about 18 g of protein per 100 g.', blocked: null, waiting_for: null, decisions: [],
  meta: { specialists: [{ name: 'nutrition', status: 'ok', steps: 1, tokens: 10, tools: ['search_foods'] }], composed: false },
}
const signedIn = () => fakeAuth({ session: fakeSession('kruthi@example.test') })

test('Home has an "Ask the coach" card whose starter questions open the chat with that question', async () => {
  fakeFetch({ 'GET /onboarding/status': { body: status('done', [], true) }, 'GET /targets/current': { body: TARGETS } })
  renderWithAuth(signedIn(), { '*': <App /> }, '/')
  const card = await screen.findByRole('region', { name: 'Ask the coach' })
  const links = within(card).getAllByRole('link')
  expect(links).toHaveLength(4)
  expect(links[0]).toHaveAttribute('href', `/chat?ask=${encodeURIComponent(SUGGESTIONS[0].message)}`)
  for (const link of links) expect(link.getAttribute('href')).toMatch(/^\/chat\?ask=/)
})

test('arriving at /chat?ask=... asks that question once, in a new chat, and shows the answer', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: REPLY } })
  renderWithAuth(signedIn(), { '*': <App /> }, '/chat?ask=How%20much%20protein%20is%20in%20paneer%3F')
  expect(await screen.findByText(/18 g of protein/)).toBeInTheDocument()
  expect(screen.getByText('How much protein is in paneer?')).toBeInTheDocument()
  expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
  expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ message: 'How much protein is in paneer?' })       // a NEW conversation: no id
})

test('React development double-run of effects does not ask the question twice', async () => {
  const calls = fakeFetch({ 'POST /chat': { body: REPLY } })
  const { render } = await import('@testing-library/react')
  const { MemoryRouter } = await import('react-router')
  const { AuthContext } = await import('../auth/context')
  render(
    <StrictMode>
      <AuthContext.Provider value={signedIn()}>
        <MemoryRouter initialEntries={['/chat?ask=hello%20there']}><App /></MemoryRouter>
      </AuthContext.Provider>
    </StrictMode>,
  )
  await screen.findByText(/18 g of protein/)
  await new Promise((r) => setTimeout(r, 50))
  expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
})

test('an ask question wins over a remembered chat, and an overlong one is cut to the limit', async () => {
  sessionStorage.setItem('coach-chat-id', 'old')
  const calls = fakeFetch({ 'POST /chat': { body: REPLY } })
  renderWithAuth(signedIn(), { '*': <App /> }, `/chat?ask=${'x'.repeat(1500)}`)
  await screen.findByText(/18 g of protein/)
  expect(calls.some((c) => c.path === '/chat/old')).toBe(false)                                                  // the old chat was not loaded
  expect((calls.find((c) => c.method === 'POST')!.body as { message: string }).message).toHaveLength(1000)
})

test('without ask the remembered chat still comes back, and the intro says what the coach can do now', async () => {
  sessionStorage.setItem('coach-chat-id', 'c9')
  fakeFetch({ 'GET /chat/c9': { body: { id: 'c9', messages: [{ id: 1, role: 'user', content: 'hi', blocked: null }, { id: 2, role: 'assistant', content: 'Hello!', blocked: null }] } } })
  renderWithAuth(signedIn(), { '*': <App /> }, '/chat')
  expect(await screen.findByText('Hello!')).toBeInTheDocument()
  expect(screen.getByText(/foods and nutrition, exercises, your own plan, targets, weight and progress, and log a meal/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
  await waitFor(() => expect(screen.queryByText('Hello!')).not.toBeInTheDocument())
})
