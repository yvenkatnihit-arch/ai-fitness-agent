import { useEffect, useState } from 'react'

// A number that counts up to its value when it appears (about 0.8 s). With "reduce motion" on, it just shows the value.
// Only the big display number uses this: the exact figures are also written out as plain text for screen readers and tests.
export function useCountUp(value: number, ms = 800): number {
  const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const [shown, setShown] = useState(0)
  useEffect(() => {
    if (reduced) return // the value is returned as it is below
    let frame = 0
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min((now - start) / ms, 1)
      setShown(Math.round(value * (1 - (1 - t) ** 3))) // ease-out
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [value, ms, reduced])
  return reduced ? value : shown
}
