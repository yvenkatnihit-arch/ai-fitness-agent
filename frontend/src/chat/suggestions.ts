// Example questions shown on an empty chat. Each one is something the coach really answers (checked by the router eval), and together they
// show every skill: foods, food rankings, your own plan, progress, exercises and logging a meal.
export const SUGGESTIONS = [
  { label: 'Protein in paneer', message: 'How much protein is in paneer?' },
  { label: 'High-protein foods', message: 'Which vegetarian foods are high in protein?' },
  { label: "Today's workout", message: 'What workout do I have today?' },
  { label: "Tomorrow's lunch", message: "What's for lunch tomorrow?" },
  { label: 'Am I on track?', message: 'Am I on track this week?' },
  { label: 'How to do a plank', message: 'How do I do a plank?' },
  { label: 'Log a meal', message: 'I ate 2 rotis and a katori of dal for lunch' },
] as const

// What to offer after an answer, by which specialist just replied (names as in backend/app/agents/menu.py). Each is a full question the
// coach can answer. After a reply that no specialist gave (a greeting, something it cannot do) the starting examples are offered again.
const AFTER: Record<string, readonly { label: string; message: string }[]> = {
  nutrition: [
    { label: 'High-protein foods', message: 'Which vegetarian foods are high in protein?' },
    { label: 'What I logged today', message: 'What have I logged today?' },
    { label: "Today's dinner", message: "What's for dinner today?" },
  ],
  my_plan: [
    { label: 'Am I on track?', message: 'Am I on track this week?' },
    { label: 'My weight progress', message: 'How much weight have I lost so far?' },
    { label: "Tomorrow's workout", message: 'What workout do I have tomorrow?' },
  ],
  exercises: [
    { label: 'Exercises for glutes', message: 'Which exercises work my glutes?' },
    { label: 'How to do a plank', message: 'How do I do a plank?' },
    { label: "Today's workout", message: 'What workout do I have today?' },
  ],
  meal_logger: [
    { label: 'What I logged today', message: 'What have I logged today?' },
    { label: 'Am I on track?', message: 'Am I on track this week?' },
  ],
}

export function followUps(specialists: readonly string[], asked: readonly string[], max = 3): readonly { label: string; message: string }[] {
  const pool = specialists.length > 0 ? (AFTER[specialists[0]] ?? SUGGESTIONS) : SUGGESTIONS
  const seen = new Set(asked.map((m) => m.trim().toLowerCase()))
  return pool.filter((s) => !seen.has(s.message.toLowerCase())).slice(0, max)
}
