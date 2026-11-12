export type Thumb = 'up' | 'down' | null

// "Was this answer helpful?" under a coach answer. Tapping the chosen thumb again takes it back. The choice is saved on the server,
// so wrong answers can be found later without reading every chat.
export function Thumbs({ value, onChange }: { value: Thumb; onChange: (next: Thumb) => void }) {
  const button = (kind: 'up' | 'down', label: string, symbol: string) => (
    <button
      type="button" aria-label={label} aria-pressed={value === kind} title={label}
      onClick={() => onChange(value === kind ? null : kind)}
      className={`rounded-full border px-2 py-0.5 text-xs transition ${
        value === kind ? 'border-brand bg-brand-soft text-brand-strong' : 'border-transparent text-muted hover:border-brand'
      }`}
    >
      {symbol}
    </button>
  )
  return (
    <div role="group" aria-label="Rate this answer" className="flex items-center gap-1">
      {button('up', 'Helpful answer', '👍')}
      {button('down', 'Not helpful', '👎')}
    </div>
  )
}
