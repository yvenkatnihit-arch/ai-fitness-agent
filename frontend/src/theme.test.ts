import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test } from 'vitest'

// Reads the real index.css (tests run from the frontend folder), so a token added to the light theme
// but forgotten in dark fails here.
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8')

function tokens(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map((m) => [m[1], m[2].toLowerCase()]))
}
const darkStart = css.indexOf('@media (prefers-color-scheme: dark)')
const light = tokens(css.slice(0, darkStart))
const dark = tokens(css.slice(darkStart, css.indexOf('@theme inline')))

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

test('dark mode defines exactly the same tokens as light mode', () => {
  expect(Object.keys(light).length).toBeGreaterThan(10)
  expect(Object.keys(dark).sort()).toEqual(Object.keys(light).sort())
})

test('every colour utility maps to a defined token', () => {
  const mapped = [...css.matchAll(/--color-([a-z0-9-]+):\s*var\(--([a-z0-9-]+)\)/g)]
  expect(mapped.length).toBeGreaterThan(10)
  for (const [, utility, token] of mapped) {
    expect(utility, 'utility name matches its token').toBe(token)
    expect(light[token], `${token} missing in light`).toBeDefined()
  }
})

// Pairs that actually appear in the app: [text, background]. Body text needs 4.5:1 (WCAG AA).
const PAIRS: [string, string][] = [
  ['ink', 'bg'], ['ink', 'surface'], ['ink-soft', 'bg'], ['ink-soft', 'surface'], ['muted', 'bg'], ['muted', 'surface'],
  ['on-brand', 'brand'], ['brand-strong', 'surface'], ['brand-strong', 'brand-soft'], ['brand-strong', 'bg'],
  ['danger', 'danger-soft'], ['danger', 'surface'], ['warn', 'warn-soft'], ['on-brand', 'ink'], ['ink-soft', 'surface-2'],
  ['muted', 'surface-2'],
]
for (const [name, theme] of [['light', light], ['dark', dark]] as const) {
  test(`text is readable in ${name} mode`, () => {
    for (const [text, background] of PAIRS) {
      expect(contrast(theme[text], theme[background]), `${text} on ${background} (${name})`).toBeGreaterThanOrEqual(4.5)
    }
  })
}
