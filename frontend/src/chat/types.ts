// What POST /chat and POST /chat/{id}/decide return (backend/app/schemas/chat.py).

export type ProposalCard = { kind: string; proposal_id: string; summary: string }

export type SpecialistRun = { name: string; status: string; steps: number; tokens: number; tools: string[] }

export type ChatMeta = { specialists?: SpecialistRun[]; composed?: boolean }

export type ChatReply = {
  conversation_id: string
  reply: string
  blocked: string | null // a guard stopped or replaced this turn (the category, never the text)
  waiting_for: ProposalCard | null // a proposal the user must approve or reject
  decisions: { proposal_id: string; choice: string; message: string }[]
  meta: ChatMeta
}

// One line in the conversation on screen.
export type ChatLine = {
  id: number
  role: 'user' | 'assistant'
  text: string
  blocked?: boolean
  meta?: ChatMeta
}

export const MAX_MESSAGE_CHARS = 1000 // the same limit as the backend (app/workflows/chat_turn.py)
