// Splits a reply into paragraphs, bullet lists and numbered lists. Pure text in, plain data out (see RichText.tsx for how it is drawn).

const BULLET = /^\s*(?:[*\-•])\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/

type Block = { kind: 'p'; text: string } | { kind: 'ul' | 'ol'; items: string[] }

export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = []
  for (const raw of text.replace(/\r/g, '').split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) continue
    const bullet = BULLET.exec(line)
    const numbered = bullet ? null : NUMBERED.exec(line)
    const kind = bullet ? 'ul' : numbered ? 'ol' : 'p'
    const content = (bullet ?? numbered)?.[1] ?? line.trim()
    const last = blocks[blocks.length - 1]
    if (kind === 'p') blocks.push({ kind: 'p', text: content })
    else if (last && last.kind === kind) last.items.push(content)
    else blocks.push({ kind, items: [content] })
  }
  return blocks
}
