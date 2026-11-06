import type { Slot } from './types'

// A sensible starting meal slot from the time of day (India time); the user can change it.
export function defaultSlot(now: Date = new Date()): Slot {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(now)
  const hour = Number(parts.find((p) => p.type === 'hour')?.value)
  const minute = Number(parts.find((p) => p.type === 'minute')?.value)
  const t = hour * 60 + minute
  if (t < 4 * 60) return 'dinner' // after midnight counts as a late dinner
  if (t < 10 * 60 + 30) return 'breakfast'
  if (t < 12 * 60) return 'mid_morning'
  if (t < 15 * 60 + 30) return 'lunch'
  if (t < 18 * 60 + 30) return 'evening_snack'
  return 'dinner'
}

// "piece" -> "piece (43 g)"; "g" stays "g".
export function unitLabel(unit: string, grams?: number): string {
  return grams === undefined ? unit : `${unit} (${Math.round(grams)} g)`
}
