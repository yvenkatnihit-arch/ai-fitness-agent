import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import { FormError, PageShell, PrimaryButton, inputClass } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { AnswerDetails } from './AnswerDetails'
import { PastChats } from './PastChats'
import { MAX_MESSAGE_CHARS, type ChatLine, type ChatReply, type ConversationDetail, type ProposalCard } from './types'

// The open chat is remembered for this browser tab, so a refresh brings it back (never anything but the id).
const STORAGE_KEY = 'coach-chat-id'
const remember = (id: string | null) => {
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // storage can be blocked (private window): the chat still works, it just is not remembered
  }
}
const remembered = () => {
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))

// Chat with the coach. The coach can answer food questions and PROPOSE a change, but nothing changes until you press Approve.
// Messages and replies are saved on the server; "New chat" starts a fresh conversation.
export function ChatPage() {
  const api = useApi()
  const [lines, setLines] = useState<ChatLine[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [card, setCard] = useState<ProposalCard | null>(null)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState<'sending' | 'deciding' | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [showPast, setShowPast] = useState(false)
  const nextId = useRef(1)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'end' }) // jsdom (tests) has no scrollIntoView
  }, [lines, card, busy])

  async function open(id: string, quiet = false) {
    setError(null)
    try {
      const chat = await api.get<ConversationDetail>(`/chat/${id}`)
      setLines(chat.messages.map((m) => ({ id: nextId.current++, role: m.role, text: m.content, blocked: m.blocked !== null })))
      setConversationId(chat.id)
      setCard(null) // a proposal still waiting from an earlier session stays on the plan screen: the chat only offers the latest turn live
      setShowPast(false)
      remember(chat.id)
    } catch (e) {
      if (quiet) remember(null) // the remembered chat is gone (deleted elsewhere): just start fresh
      else setError(asApiError(e))
    }
  }

  useEffect(() => {
    const id = remembered()
    if (id) void open(id, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on arrival
  }, [])

  const add = (role: ChatLine['role'], text: string, extra: Partial<ChatLine> = {}) =>
    setLines((current) => [...current, { id: nextId.current++, role, text, ...extra }])

  function show(reply: ChatReply) {
    setConversationId(reply.conversation_id)
    remember(reply.conversation_id)
    add('assistant', reply.reply, { blocked: reply.blocked !== null, meta: reply.meta })
    setCard(reply.waiting_for)
  }

  async function send(event?: FormEvent) {
    event?.preventDefault()
    const text = draft.trim()
    if (!text || busy) return
    setBusy('sending')
    setError(null)
    setCard(null) // a card belongs to the latest turn: a new message leaves the old proposal waiting on the plan screen
    add('user', text)
    setDraft('')
    try {
      show(await api.post<ChatReply>('/chat', { message: text, ...(conversationId ? { conversation_id: conversationId } : {}) }))
    } catch (e) {
      setError(asApiError(e))
      setDraft(text) // keep what they typed so they can send it again
      setLines((current) => current.slice(0, -1)) // and take the unsent message back off the screen
    } finally {
      setBusy(null)
    }
  }

  async function decide(choice: 'approve' | 'reject') {
    if (!conversationId || busy) return
    setBusy('deciding')
    setError(null)
    try {
      show(await api.post<ChatReply>(`/chat/${conversationId}/decide`, { choice }))
    } catch (e) {
      const failure = asApiError(e)
      setError(failure)
      if (failure.status === 409) setCard(null) // it was already answered or is no longer waiting
    } finally {
      setBusy(null)
    }
  }

  function newChat() {
    remember(null)
    setLines([])
    setConversationId(null)
    setCard(null)
    setDraft('')
    setError(null)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <PageShell
      title="Coach chat"
      back
    >
      <p className="text-xs text-muted">
        Ask about foods, calories and protein. The coach can make mistakes, and for medical questions please ask a doctor. Any plan change it
        suggests only happens if you approve it.
      </p>

      <button
        type="button" onClick={() => setShowPast((v) => !v)} aria-expanded={showPast}
        className="self-start text-sm font-semibold text-brand-strong"
      >
        {showPast ? 'Hide past chats' : 'Past chats'}
      </button>
      {showPast && <PastChats currentId={conversationId} onOpen={(id) => void open(id)} onDeleted={(id) => { if (id === conversationId) newChat() }} />}

      <section aria-label="Conversation" className="flex min-h-48 flex-col gap-2">
        {lines.length === 0 && <p className="text-sm text-ink-soft">Try: &ldquo;How much protein is in paneer?&rdquo;</p>}
        {lines.map((line) => (
          <div key={line.id} className={`flex flex-col gap-1 ${line.role === 'user' ? 'items-end' : 'items-start'}`}>
            <p
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                line.role === 'user' ? 'bg-brand text-on-brand' : line.blocked ? 'bg-warn-soft text-warn' : 'bg-surface text-ink shadow-sm'
              }`}
            >
              {line.text}
            </p>
            {line.meta && <AnswerDetails meta={line.meta} />}
          </div>
        ))}
        {busy === 'sending' && <p role="status" className="text-sm text-muted">The coach is thinking…</p>}
        <div ref={bottom} />
      </section>

      {card && (
        <section aria-label="Proposal waiting for your answer" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm ring-2 ring-brand">
          <h2 className="text-base font-bold text-ink">The coach suggests a change</h2>
          <p className="text-sm text-ink-soft">{card.summary}</p>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button" onClick={() => decide('reject')} disabled={busy !== null}
              className="rounded-xl border border-line px-4 py-3 font-semibold text-ink-soft transition hover:bg-surface-2 disabled:opacity-50"
            >
              Reject
            </button>
            <PrimaryButton type="button" onClick={() => decide('approve')} busy={busy === 'deciding'} disabled={busy !== null}>
              Approve
            </PrimaryButton>
          </div>
        </section>
      )}

      {error && <FormError message={error.message} requestId={error.requestId} />}

      <form onSubmit={send} className="flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-ink-soft">
          Your message
          <textarea
            className={inputClass} rows={3} maxLength={MAX_MESSAGE_CHARS} value={draft}
            onChange={(e) => setDraft(e.target.value)} onKeyDown={onKeyDown} placeholder="Ask the coach…"
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button" onClick={newChat} disabled={busy !== null || lines.length === 0}
            className="rounded-xl border border-line px-4 py-3 font-semibold text-ink-soft transition hover:bg-surface-2 disabled:opacity-50"
          >
            New chat
          </button>
          <PrimaryButton type="submit" disabled={!draft.trim() || busy !== null}>Send</PrimaryButton>
        </div>
      </form>
    </PageShell>
  )
}
