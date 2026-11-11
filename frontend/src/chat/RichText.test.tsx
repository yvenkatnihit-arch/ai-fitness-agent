import { expect, test } from 'vitest'

import { parseBlocks } from './richTextParse'

test('plain text lines become paragraphs and blank lines are dropped', () => {
  expect(parseBlocks('Hello\n\nWorld')).toEqual([{ kind: 'p', text: 'Hello' }, { kind: 'p', text: 'World' }])
})

test('consecutive bullets of any common marker form one list, and numbered lines form an ordered list', () => {
  expect(parseBlocks('* a\n- b\n• c')).toEqual([{ kind: 'ul', items: ['a', 'b', 'c'] }])
  expect(parseBlocks('1. one\n2) two')).toEqual([{ kind: 'ol', items: ['one', 'two'] }])
})

test('a paragraph between two lists splits them, and indentation and carriage returns are tolerated', () => {
  expect(parseBlocks('* a\r\nText\r\n  * b')).toEqual([{ kind: 'ul', items: ['a'] }, { kind: 'p', text: 'Text' }, { kind: 'ul', items: ['b'] }])
})

test('a dash inside a sentence or a number with a decimal point is not mistaken for a list', () => {
  expect(parseBlocks('Paneer - 18 g protein')).toEqual([{ kind: 'p', text: 'Paneer - 18 g protein' }])
  expect(parseBlocks('3.5 g of fat')).toEqual([{ kind: 'p', text: '3.5 g of fat' }])
})

test('empty input has no blocks', () => {
  expect(parseBlocks('')).toEqual([])
  expect(parseBlocks('   \n  ')).toEqual([])
})
