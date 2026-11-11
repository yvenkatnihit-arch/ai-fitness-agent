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
