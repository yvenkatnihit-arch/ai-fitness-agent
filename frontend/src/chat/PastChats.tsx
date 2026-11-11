import { useEffect, useState } from 'react'

import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import type { ConversationSummary } from './types'

const when = (iso: string) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })

// The list of the person's earlier chats. Opening one loads it into the chat; deleting one removes it (and its saved state) for good.
export function PastChats({ currentId, onOpen, onDeleted }: {
  currentId: string | null
  onOpen: (id: string) => void
  onDeleted: (id: string) => void
}) {
  const api = useApi()
  const [chats, setChats] = useState<ConversationSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api.get<{ conversations: ConversationSummary[] }>('/chat').then(
      (r) => { if (!cancelled) setChats(r.conversations) },
      (e: unknown) => { if (!cancelled) setError(e instanceof ApiError ? e.message : 'Could not load your chats.') },
    )
    return () => { cancelled = true }
  }, [api, currentId]) // reload when a new chat becomes the current one, so it shows up in the list

  async function remove(id: string) {
    setError(null)
    try {
      await api.delete(`/chat/${id}`)
      setChats((current) => current?.filter((c) => c.id !== id) ?? null)
      onDeleted(id)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not delete that chat.')
    }
  }

  return (
    <section aria-label="Past chats" className="flex flex-col gap-2 rounded-2xl bg-surface p-3 shadow-sm">
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {chats === null && !error && <p className="text-sm text-muted">Loading…</p>}
      {chats?.length === 0 && <p className="text-sm text-muted">No earlier chats yet.</p>}
      <ul className="flex flex-col gap-1">
        {chats?.map((chat) => (
          <li key={chat.id} className="flex items-center justify-between gap-2">
            <button
              type="button" onClick={() => onOpen(chat.id)} aria-current={chat.id === currentId ? 'true' : undefined}
              className={`min-w-0 flex-1 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface-2 ${chat.id === currentId ? 'font-semibold text-brand-strong' : 'text-ink'}`}
            >
              <span className="block truncate">{chat.title ?? 'Chat'}</span>
              <span className="block text-xs text-muted">{when(chat.updated_at)}</span>
            </button>
            <button
              type="button" onClick={() => remove(chat.id)} aria-label={`Delete chat: ${chat.title ?? 'Chat'}`}
              className="shrink-0 rounded-lg border border-line px-2 py-1 text-xs text-ink-soft hover:bg-surface-2"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
