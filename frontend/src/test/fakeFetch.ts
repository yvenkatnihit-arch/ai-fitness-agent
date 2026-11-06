// Replace window.fetch with canned backend answers. Keys look like "GET /onboarding/status".
// A value is either a response, or a function of the request body returning one.
import { vi } from 'vitest'

type Reply = { status?: number; body: unknown }
type Handler = Reply | ((body: unknown) => Reply)

export function fakeFetch(handlers: Record<string, Handler>) {
  const calls: { method: string; path: string; query: string; body: unknown; headers: Record<string, string> }[] = []

  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET'
    const { pathname: path, search: query } = new URL(url)
    const body = init.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, query, body, headers: (init.headers ?? {}) as Record<string, string> })

    const handler = handlers[`${method} ${path}`]
    if (!handler) throw new Error(`fakeFetch: no handler for ${method} ${path}`)
    const reply = typeof handler === 'function' ? handler(body) : handler
    const status = reply.status ?? 200
    return new Response(status === 204 ? null : JSON.stringify(reply.body), {
      status,
      headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'req-test-1234' },
    })
  })

  vi.stubGlobal('fetch', fetchMock)
  return calls
}

export function status(nextStep: string, done: string[] = [], completed = false) {
  const steps = ['consent', 'basics', 'goal', 'preferences', 'training', 'screening']
  return { ...Object.fromEntries(steps.map((s) => [s, done.includes(s)])), completed, next_step: nextStep }
}
