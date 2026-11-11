import { Link } from 'react-router'

// The round "ask the coach" button that floats at the bottom-left of signed-in screens and opens the chat (like the assistant button
// in food-delivery apps). It lines up with the page column, not the screen edge, so on a wide screen it stays next to the content.
// The soft ring pulses three times to be noticed, then stops; people who prefer less motion never see it move.
export function ChatBubble() {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-20">
      <div className="mx-auto w-full max-w-md px-4">
        <Link
          to="/chat"
          aria-label="Chat with the coach"
          title="Chat with the coach"
          className="pointer-events-auto relative flex h-14 w-14 items-center justify-center rounded-full bg-brand text-on-brand shadow-lg ring-2 ring-surface transition hover:opacity-90 active:scale-95"
        >
          <span
            aria-hidden="true"
            className="absolute inset-0 rounded-full bg-brand opacity-40 motion-safe:animate-ping"
            style={{ animationIterationCount: 3 }}
          />
          <svg aria-hidden="true" viewBox="0 0 24 24" className="relative h-7 w-7" fill="currentColor">
            <path d="M12 2l2.2 6.3L20.5 10.5l-6.3 2.2L12 19l-2.2-6.3L3.5 10.5l6.3-2.2L12 2z" />
            <path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z" />
          </svg>
        </Link>
      </div>
    </div>
  )
}
