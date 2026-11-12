import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useSearchParams } from 'react-router'

import { FormError, PageShell, PrimaryButton, inputClass } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { AnswerDetails } from './AnswerDetails'
import { PastChats } from './PastChats'
import { PromptCards } from './PromptCards'
import { RichText } from './RichText'
import { Thumbs, type Thumb } from './Thumbs'
import { followUps } from './suggestions'
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

const SLOW_AFTER_SECONDS = 10
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
  const [seconds, setSeconds] = useState(0)
  const nextId = useRef(1)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'end' }) // jsdom (tests) has no scrollIntoView
  }, [lines, card, busy])

  // How long this question has been running. Honest: it only counts seconds, it does not pretend to know which step the coach is on.
  useEffect(() => {
    if (busy !== 'sending') return
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.round((Date.now() - started) / 1000)), 1000)
    return () => {
      clearInterval(timer)
      setSeconds(0)
    }
  }, [busy])

  async function open(id: string, quiet = false) {
    setError(null)
    try {
      const chat = await api.get<ConversationDetail>(`/chat/${id}`)
      setLines(chat.messages.map((m) => ({ id: nextId.current++, role: m.role, text: m.content, blocked: m.blocked !== null,
        ...(m.role === 'assistant' ? { messageId: m.id, feedback: m.feedback ?? null } : {}) })))
      setConversationId(chat.id)
      setCard(null) // a proposal still waiting from an earlier session stays on the plan screen: the chat only offers the latest turn live
      setShowPast(false)
      remember(chat.id)
    } catch (e) {
      if (quiet) remember(null) // the remembered chat is gone (deleted elsewhere): just start fresh
      else setError(asApiError(e))
    }
  }

  // Arriving with /chat?ask=... (the starter questions on Home) starts a NEW chat with that question; otherwise the remembered chat comes back.
  // The ref stops React's development double-run of effects from asking the question twice.
  const [params, setParams] = useSearchParams()
  const arrived = useRef(false)
  useEffect(() => {
    if (arrived.current) return
    arrived.current = true
    const ask = params.get('ask')?.trim().slice(0, MAX_MESSAGE_CHARS)
    if (ask) {
      remember(null)
      setParams({}, { replace: true }) // so a refresh does not ask it again
      void send(undefined, ask)
      return
    }
    const id = remembered()
    if (id) void open(id, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on arrival
  }, [])

  const add = (role: ChatLine['role'], text: string, extra: Partial<ChatLine> = {}) =>
    setLines((current) => [...current, { id: nextId.current++, role, text, ...extra }])

  // A thumb shows at once and is saved in the background; if saving fails it goes back and the error is shown.
  async function rate(line: ChatLine, next: Thumb) {
    const before = line.feedback ?? null
    const set = (value: Thumb) => setLines((current) => current.map((l) => (l.id === line.id ? { ...l, feedback: value } : l)))
    set(next)
    try {
      await api.put(`/chat/messages/${line.messageId}/feedback`, { value: next })
    } catch (e) {
      set(before)
      setError(asApiError(e))
    }
  }

  function show(reply: ChatReply) {
    setConversationId(reply.conversation_id)
    remember(reply.conversation_id)
    add('assistant', reply.reply, { blocked: reply.blocked !== null, meta: reply.meta, ...(reply.message_id ? { messageId: reply.message_id, feedback: null } : {}) })
    setCard(reply.waiting_for)
  }

  async function send(event?: FormEvent, example?: string) {
    event?.preventDefault()
    const text = (example ?? draft).trim()
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

  // After an answer: a few next questions chosen from which specialist just replied (never ones already asked in this chat).
  const last = lines[lines.length - 1]
  const more = !busy && !card && last?.role === 'assistant'
    ? followUps(last.meta?.specialists?.map((s) => s.name) ?? [], lines.filter((l) => l.role === 'user').map((l) => l.text))
    : []

  return (
    <PageShell
      title="Coach chat"
      back
    >
      <div className="glass flex items-start gap-3 rounded-2xl p-4">
        <span aria-hidden="true" className="ring-glow mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-brand" />
        <p className="text-xs text-ink-soft">
          I can answer questions about foods and nutrition, exercises, your own plan, targets, weight and progress, and log a meal for you.
          The coach can make mistakes, and for medical questions please ask a doctor. Anything it suggests saving only happens if you approve it.
        </p>
      </div>

      <button
        type="button" onClick={() => setShowPast((v) => !v)} aria-expanded={showPast}
        className="self-start text-sm font-semibold text-brand-strong"
      >
        {showPast ? 'Hide past chats' : 'Past chats'}
      </button>
      {showPast && <PastChats currentId={conversationId} onOpen={(id) => void open(id)} onDeleted={(id) => { if (id === conversationId) newChat() }} />}

      <section aria-label="Conversation" className="flex min-h-48 flex-col gap-2">
        {lines.length === 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-ink-soft">Not sure what to ask? Tap an example:</p>
            <PromptCards disabled={busy !== null} onPick={(message) => void send(undefined, message)} />
          </div>
        )}
        {lines.map((line) => (
          <div key={line.id} className={`flex flex-col gap-1 ${line.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div
              data-bubble={line.role === 'user' ? 'user' : line.blocked ? 'notice' : 'coach'}
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                line.role === 'user' ? 'rounded-br-md bg-brand text-on-brand' : line.blocked ? 'bg-warn-soft text-warn' : 'glass rounded-bl-md text-ink'
              }`}
            >
              {line.role === 'user' ? line.text : <RichText text={line.text} />}
            </div>
            {line.role === 'assistant' && !line.blocked && line.messageId && (
              <Thumbs value={line.feedback ?? null} onChange={(next) => void rate(line, next)} />
            )}
            {line.meta && <AnswerDetails meta={line.meta} />}
          </div>
        ))}
        {busy === 'sending' && (
          <p role="status" className="flex items-center gap-2 text-sm text-muted">
            <span aria-hidden="true" className="flex gap-1">
              <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
            </span>
            The coach is thinking… {seconds > 0 ? `${seconds} s` : ''}
            {seconds >= SLOW_AFTER_SECONDS && ' Still working: the AI service can be slow at times.'}
          </p>
        )}
        {more.length > 0 && (
          <ul aria-label="Suggested next questions" className="flex flex-wrap gap-2">
            {more.map((s) => (
              <li key={s.label}>
                <button
                  type="button" title={s.message} onClick={() => void send(undefined, s.message)}
                  className="rounded-full border border-brand bg-brand-soft px-3 py-1.5 text-sm font-medium text-brand-strong transition hover:opacity-90"
                >
                  {s.label}
                </button>
              </li>
            ))}
          </ul>
        )}
        <div ref={bottom} />
      </section>

      {card && (
        <section aria-label="Proposal waiting for your answer" className="glass flex flex-col gap-3 rounded-2xl p-4 ring-2 ring-brand">
          <h2 className="text-base font-bold text-ink">Please confirm</h2>
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
