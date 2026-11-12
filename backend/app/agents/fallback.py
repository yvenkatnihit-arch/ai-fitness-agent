"""What the coach says when no specialist fits the message (Step 7.11g, D-102). Plain code, no model, so it is free and cannot be
steered by the user's text.

Before this module every message no specialist took got the same canned reply, which felt broken
("hello", "make me a workout plan" and "what should I eat today" all said the same thing). The reply now depends on what was asked and
says which screen does it. As more specialists are added, the topics they take over simply stop reaching this fallback."""

import re

NOTHING_FITS = ("I can help with foods and their nutrition, exercises, your own plan, targets, weight and progress, and logging a meal "
                "(you confirm it first). What would you like to know?")

EXAMPLES = "Try asking, for example, “How much protein is in paneer?”, “What workout do I have today?” or “How do I do a plank?”."

# (name, pattern, reply). The first match wins, so the more specific topics come first.
TOPICS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("workout", re.compile(r"\b(workout|work out|exercise|exercises|gym|squat|squats|bench|deadlift|reps?|sets?|split|training|cardio|stretch\w*|muscle)\b"),
     "I cannot build or change workouts in chat yet. Your Workout plan and Workout split screens do that, and you approve every change. "
     "In chat I can answer questions about exercises and tell you what is in your own workout plan. " + EXAMPLES),
    ("meal_plan", re.compile(r"\b(meal plan|diet plan|menu|what (should|can|do) i (eat|have)|what to eat|eat today|breakfast ideas?|lunch ideas?|dinner ideas?|recipes?)\b"),
     "I cannot plan your meals in chat yet. Your Meal plan screen builds a full week that fits your targets, and you approve it first. "
     "In chat I can tell you about any food, and what your meal plan says for a day. " + EXAMPLES),
    ("logging", re.compile(r"\b(log|logged|logging|track|tracked|i (ate|had|eaten)|add (a|my) meal)\b"),
     "To log a meal, tell me what you ate, for example “I ate 2 rotis and a katori of dal for lunch” (you confirm it before it is saved), or use the "
     "Log a meal screen. Your weight is logged on the Home screen. " + EXAMPLES),
    ("targets", re.compile(r"\b(target|targets|goal|goals|my weight|weigh|losing weight|gaining weight|weight loss|bmi|bmr|tdee|progress|how many calories (should|do) i|lose weight|gain weight)\b"),
     "Your daily targets and goal date are on the Home screen, worked out by code from your details. You can change your details in Settings. "
     "In chat I can tell you your targets, your weight progress and what you have logged. " + EXAMPLES),
    ("settings", re.compile(r"\b(settings?|profile|change my (diet|details|goal|cuisine)|allerg\w*|dislikes?)\b"),
     "You can change your diet, cuisines, dislikes and details in Settings. In chat I can answer questions about foods, exercises and your own plan. " + EXAMPLES),
)
GREETING = re.compile(r"^\s*(hi+|hello+|hey+|hola|namaste|good (morning|afternoon|evening)|yo|sup|howdy)\b[\s!.,?]*(there|coach)?[\s!.,?]*$")
THANKS = re.compile(r"^\s*(thanks|thank you|thx|ty|cool|ok|okay|great|nice|got it|awesome)\b[\s!.,?]*$")
GREETING_REPLY = "Hi! I am your fitness coach. I can answer questions about foods, exercises, your plan and progress, and log a meal for you. " + EXAMPLES
THANKS_REPLY = "You are welcome! Ask me anything about your food, workouts or progress whenever you like."


# Asking the coach to MAKE a plan or diet. The chat cannot do this, so code answers (never the router, never a specialist): see D-119.
MAKE_PLAN = re.compile(
    r"\b(?:make|create|build|prepare|generate|design|draw up|write|set up|suggest|give me)\b.{0,30}"
    r"\b(?:plan|diet|diet chart|meal plan|workout plan|routine|menu|programme|program)\b"
    r"|\b(?:diet|plan|routine|programme|program)\b.{0,12}\b(?:for me|for muscle|for fat|for weight|to lose|to gain|to build)\b"
    r"|\bi (?:want|need) (?:a |an |some )?(?:new )?(?:diet|plan|workout|routine)\b")
MAKE_PLAN_REPLY = ("I cannot create plans in chat. Use the Meal plan screen for a 7-day meal plan and the Workout plan screen for a workout plan: "
                   "each is built from your targets and preferences, and nothing is saved until you approve it. "
                   "In chat I can answer questions about foods and exercises, and tell you what is in your current plan. " + EXAMPLES)


def asks_for_a_plan(message: str) -> bool:
    return bool(MAKE_PLAN.search(" ".join(message.lower().split())))


def nothing_fits_reply(message: str) -> str:
    """The reply for a message no specialist took. Always fixed text, chosen by simple patterns."""
    text = " ".join(message.lower().split())
    if GREETING.match(text):
        return GREETING_REPLY
    if THANKS.match(text):
        return THANKS_REPLY
    if asks_for_a_plan(text):      # the screen for what was asked; both screens when it is not clear which
        for _, pattern, reply in TOPICS[:2]:
            if pattern.search(text):
                return reply
        return MAKE_PLAN_REPLY
    for _, pattern, reply in TOPICS:
        if pattern.search(text):
            return reply
    return NOTHING_FITS
