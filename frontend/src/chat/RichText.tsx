import type { ReactNode } from 'react'

import { parseBlocks } from './richTextParse'

// Replies from the coach are plain text with a little structure: "* item" or "- item" bullets, "1. step" numbered steps, and **bold**.
// This turns that into proper lists and bold text. It builds React elements only (never raw HTML), so whatever a reply contains is shown as
// text and can never run as code.

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

export function RichText({ text }: { text: string }) {
  const blocks = parseBlocks(text)
  return (
    <div className="flex flex-col gap-1.5">
      {blocks.map((block, i) => {
        if (block.kind === 'p') return <p key={i}>{inline(block.text)}</p>
        const Tag = block.kind
        return (
          <Tag key={i} className={`${block.kind === 'ul' ? 'list-disc' : 'list-decimal'} flex flex-col gap-0.5 pl-5`}>
            {block.items.map((item, j) => <li key={j}>{inline(item)}</li>)}
          </Tag>
        )
      })}
    </div>
  )
}
