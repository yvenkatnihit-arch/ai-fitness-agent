import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test } from 'vitest'

// Reads the real index.css (tests run from the frontend folder). The app is dark only (redesign, D-121).
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8')

function tokens(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map((m) => [m[1], m[2].toLowerCase()]))
}
const theme = tokens(css.slice(0, css.indexOf('@theme inline')))

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

test('the theme defines the colour tokens, and there is no light or system-dark variant left to drift', () => {
  expect(Object.keys(theme).length).toBeGreaterThan(10)
  expect(css).not.toContain('prefers-color-scheme')
})

test('the brand is neon lime and text on it is the dark background colour', () => {
  expect(theme.brand).toBe('#b7ff35')
  expect(theme['on-brand']).toBe(theme.bg)
})

test('every colour utility maps to a defined token', () => {
  const mapped = [...css.matchAll(/--color-([a-z0-9-]+):\s*var\(--([a-z0-9-]+)\)/g)]
  expect(mapped.length).toBeGreaterThan(10)
  for (const [, utility, token] of mapped) {
    expect(utility, 'utility name matches its token').toBe(token)
    expect(theme[token], `${token} missing`).toBeDefined()
  }
})

// Pairs that actually appear in the app: [text, background]. Body text needs 4.5:1 (WCAG AA).
const PAIRS: [string, string][] = [
  ['ink', 'bg'], ['ink', 'surface'], ['ink-soft', 'bg'], ['ink-soft', 'surface'], ['muted', 'bg'], ['muted', 'surface'],
  ['on-brand', 'brand'], ['brand-strong', 'surface'], ['brand-strong', 'brand-soft'], ['brand-strong', 'bg'],
  ['danger', 'danger-soft'], ['danger', 'surface'], ['warn', 'warn-soft'], ['on-brand', 'ink'], ['ink-soft', 'surface-2'],
  ['muted', 'surface-2'],
]
test('text is readable (WCAG AA, 4.5:1) for every pairing used in the app', () => {
  for (const [text, background] of PAIRS) {
    expect(contrast(theme[text], theme[background]), `${text} on ${background}`).toBeGreaterThanOrEqual(4.5)
  }
})
