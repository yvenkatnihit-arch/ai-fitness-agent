import { useEffect, useRef, useState, type ReactNode } from 'react'

// Two or more full-width panes side by side: swipe left (or use the tabs) to move to the next. Used on Home: "Today" first, then
// "Daily targets". It is plain CSS scroll-snap, so a thumb swipe feels native; the tabs are for mouse and keyboard users and also show
// where you are. Both panes are always in the page, so nothing is hidden from screen readers.
export function SwipePanes({ labels, children }: { labels: readonly string[]; children: ReactNode[] }) {
  const track = useRef<HTMLDivElement>(null)
  const panes = useRef<(HTMLDivElement | null)[]>([])
  const [active, setActive] = useState(0)
  const [height, setHeight] = useState<number | undefined>(undefined)

  // The track is only as tall as the pane you are on, so the short "targets" pane does not leave a long empty page under it.
  useEffect(() => {
    const pane = panes.current[active]
    if (!pane || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => setHeight(pane.offsetHeight))
    observer.observe(pane)
    return () => observer.disconnect()
  }, [active])

  function onScroll() {
    const el = track.current
    if (!el) return
    const index = Math.round(el.scrollLeft / (el.clientWidth || 1))
    setActive(Math.max(0, Math.min(labels.length - 1, index)))
  }

  function go(index: number) {
    const el = track.current
    el?.scrollTo?.({ left: index * (el.clientWidth || 0), behavior: 'smooth' })
    setActive(index)
  }

  return (
    <div className="flex flex-col gap-3">
      <div role="tablist" aria-label="Home sections" className="glass flex gap-1 rounded-full p-1">
        {labels.map((label, i) => (
          <button
            key={label} type="button" role="tab" id={`pane-tab-${i}`} aria-selected={active === i} aria-controls={`pane-${i}`}
            onClick={() => go(i)}
            className={`flex-1 rounded-full px-3 py-1.5 text-sm font-semibold transition ${active === i ? 'bg-brand text-on-brand' : 'text-ink-soft'}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div
        ref={track} onScroll={onScroll} style={{ height }}
        className="no-scrollbar flex snap-x snap-mandatory items-start overflow-x-auto overscroll-x-contain scroll-smooth"
      >
        {children.map((child, i) => (
          <div
            key={labels[i]} id={`pane-${i}`} role="tabpanel" aria-labelledby={`pane-tab-${i}`}
            ref={(node) => { panes.current[i] = node }}
            className="flex w-full shrink-0 snap-start flex-col gap-3 px-px"
          >
            {child}
          </div>
        ))}
      </div>
      {active < labels.length - 1 && <p className="text-center text-xs text-muted">Swipe left for your {labels[active + 1].toLowerCase()}</p>}
    </div>
  )
}
