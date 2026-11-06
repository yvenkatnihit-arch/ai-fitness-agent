// Calls to our FastAPI backend. Attaches the login token and turns our error format
// ({detail, errors?, request_id}, D-035) into an ApiError the screens can show.

const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  status: number // 0 = couldn't reach the server
  fieldErrors: Record<string, string> // e.g. { height_cm: "..." } from a 422
  requestId: string | null

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}, requestId: string | null = null) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors
    this.requestId = requestId
  }
}

export const UNREACHABLE =
  "Can't reach the server. If the app was idle, it may be waking up: please try again in a minute."

type ErrorBody = { detail?: unknown; errors?: { field: string; message: string }[]; request_id?: string }

export type Api = {
  get: <T>(path: string) => Promise<T>
  put: <T>(path: string, body: unknown) => Promise<T>
  post: <T>(path: string, body?: unknown) => Promise<T>
  delete: (path: string) => Promise<void>
}

export function createApi(accessToken: string | null): Api {
  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {}
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`
    if (body !== undefined) headers['Content-Type'] = 'application/json'

    let response: Response
    try {
      response = await fetch(`${BASE_URL}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch {
      throw new ApiError(0, UNREACHABLE)
    }

    if (response.status === 204) return undefined as T // "No Content": e.g. a successful delete
    if (response.ok) return (await response.json()) as T

    let data: ErrorBody = {}
    try {
      data = (await response.json()) as ErrorBody
    } catch {
      // not JSON (e.g. a proxy error page); fall through to a generic message
    }
    const message = typeof data.detail === 'string' ? data.detail : 'Something went wrong. Please try again.'
    const fieldErrors = Object.fromEntries((data.errors ?? []).map((e) => [e.field, e.message]))
    throw new ApiError(response.status, message, fieldErrors, data.request_id ?? response.headers.get('x-request-id'))
  }

  return {
    get: (path) => request('GET', path),
    put: (path, body) => request('PUT', path, body),
    post: (path, body) => request('POST', path, body),
    delete: (path) => request<void>('DELETE', path),
  }
}
