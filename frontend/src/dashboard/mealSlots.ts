import { defaultSlot } from '../meals/slots'
import type { PlannedMeal, Today } from './types'

// The day's meal slots in the order they happen, and their names on screen.
export const SLOT_ORDER = ['breakfast', 'mid_morning', 'lunch', 'evening_snack', 'dinner'] as const
export const SLOT_LABEL: Record<string, string> = {
  breakfast: 'Breakfast', mid_morning: 'Mid-morning', lunch: 'Lunch', evening_snack: 'Evening snack', dinner: 'Dinner',
}
export const slotLabel = (slot: string) => SLOT_LABEL[slot] ?? slot.replace('_', ' ')
const place = (slot: string) => (SLOT_ORDER as readonly string[]).indexOf(slot) === -1 ? 99 : (SLOT_ORDER as readonly string[]).indexOf(slot)

// The meals to tick off: the slots in today's plan, or the four everyone knows when there is no plan.
export function checklistSlots(today: Today): string[] {
  const planned = today.meal_plan?.meals.map((m) => m.slot) ?? []
  const slots = planned.length > 0 ? planned : ['breakfast', 'lunch', 'evening_snack', 'dinner']
  return [...slots].sort((a, b) => place(a) - place(b))
}

export const loggedSlots = (today: Today): Set<string> => new Set(today.logged.map((m) => m.slot))

// The next planned meal that is not logged yet and has not passed (the time of day comes from the same rule as the log screen's default).
export function nextPlannedMeal(today: Today, now: Date = new Date()): PlannedMeal | null {
  if (!today.meal_plan) return null
  const done = loggedSlots(today)
  const current = place(defaultSlot(now))
  return [...today.meal_plan.meals].sort((a, b) => place(a.slot) - place(b.slot)).find((m) => place(m.slot) >= current && !done.has(m.slot)) ?? null
}

// How many calories are left (or over) today. Both numbers come from the server; this is one subtraction, rounded.
export function kcalLeft(eaten: number, target: number): { amount: number; over: boolean } {
  const left = Math.round(target) - Math.round(eaten)
  return { amount: Math.abs(left), over: left < 0 }
}
