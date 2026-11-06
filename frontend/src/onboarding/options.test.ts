/// <reference types="node" />
// The frontend's option VALUES must match the backend's Python definitions exactly.
// If someone adds a choice on one side only, this fails (the backend would reject it with a 422).
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test } from 'vitest'

import * as options from './options'

// Tests run from frontend/, so the backend is one folder up. (Built with node:path on purpose:
// Vite would treat `new URL(..., import.meta.url)` as an asset import and refuse files outside frontend/.)
const backend = (path: string) => readFileSync(resolve(process.cwd(), '..', 'backend', path), 'utf-8')

// Values of `Name = Literal[...]` (or `NAME: Final = (...)`) in a Python file.
function pythonValues(file: string, name: string): string[] {
  const source = backend(file)
  const block = source.match(new RegExp(`${name}(?:: Final)? = (?:Literal\\[|\\()([\\s\\S]*?)[\\])]`))
  if (!block) throw new Error(`${name} not found in ${file}`)
  return [...block[1].matchAll(/"(\w+)"/g)].map((m) => m[1])
}

const values = (list: readonly (readonly string[])[]) => list.map((item) => item[0])

test.each([
  ['SEXES', 'app/safety/safety_config.py', 'Sex'],
  ['ACTIVITY_LEVELS', 'app/calc/tdee.py', 'ActivityLevel'],
  ['GOALS', 'app/calc/targets.py', 'Goal'],
  ['DIETS', 'app/core/vocabulary.py', 'DietType'],
  ['PACES', 'app/core/vocabulary.py', 'Pace'],
  ['CUISINES', 'app/core/vocabulary.py', 'Cuisine'],
  ['EXPERIENCE', 'app/core/vocabulary.py', 'ExperienceLevel'],
  ['LOCATIONS', 'app/core/vocabulary.py', 'WorkoutLocation'],
  ['EQUIPMENT', 'app/core/vocabulary.py', 'Equipment'],
  ['INJURY_AREAS', 'app/core/vocabulary.py', 'InjuryArea'],
  ['SCREENING_QUESTIONS', 'app/safety/safety_config.py', 'SCREENING_FLAGS'],
] as const)('%s matches %s %s', (frontendName, file, pythonName) => {
  const frontend = values(options[frontendName] as readonly (readonly string[])[])
  expect(new Set(frontend)).toEqual(new Set(pythonValues(file, pythonName)))
})
