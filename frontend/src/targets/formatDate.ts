// "2026-11-06" -> "6 Nov 2026". Built from the parts, so the browser's timezone can't shift the day.
export function formatDate(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
