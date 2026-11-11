"""What the coach says when no specialist fits the message (Step 7.11g, D-102). Plain code, no model, so it is free and cannot be
steered by the user's text.

Today the chat has ONE specialist (nutrition). Before this module every other message got the same canned reply, which felt broken
("hello", "make me a workout plan" and "what should I eat today" all said the same thing). The reply now depends on what was asked and
says which screen does it. As more specialists are added, the topics they take over simply stop reaching this fallback."""

import re

NOTHING_FITS = ("I can help with questions about foods and dishes for now, such as calories, protein and portion sizes. "
                "What would you like to know?")

EXAMPLES = "Try asking, for example, “How much protein is in paneer?” or “Calories in 2 rotis”."

# (name, pattern, reply). The first match wins, so the more specific topics come first.
TOPICS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("workout", re.compile(r"\b(workout|work out|exercise|exercises|gym|squat|squats|bench|deadlift|reps?|sets?|split|training|cardio|stretch\w*|muscle)\b"),
     "I cannot build or change workouts in chat yet. Your Workout plan and Workout split screens do that, and you approve every change. "
     "In chat I can answer questions about foods. " + EXAMPLES),
    ("meal_plan", re.compile(r"\b(meal plan|diet plan|menu|what (should|can|do) i (eat|have)|what to eat|eat today|breakfast ideas?|lunch ideas?|dinner ideas?|recipes?)\b"),
     "I cannot plan your meals in chat yet. Your Meal plan screen builds a full week that fits your targets, and you approve it first. "
     "In chat I can tell you about any food. " + EXAMPLES),
    ("logging", re.compile(r"\b(log|logged|logging|track|tracked|i (ate|had|eaten)|add (a|my) meal)\b"),
     "Logging a meal is on the Log a meal screen for now, where you pick the foods and amounts. In chat I can tell you what is in a food. "
     + EXAMPLES),
    ("targets", re.compile(r"\b(target|targets|goal|goals|my weight|weigh|bmi|bmr|tdee|progress|how many calories (should|do) i|lose weight|gain weight)\b"),
     "Your daily targets and goal date are on the Home screen, worked out by code from your details. You can change your details in Settings. "
     "In chat I can answer questions about foods. " + EXAMPLES),
    ("settings", re.compile(r"\b(settings?|profile|change my (diet|details|goal|cuisine)|allerg\w*|dislikes?)\b"),
     "You can change your diet, cuisines, dislikes and details in Settings. In chat I can answer questions about foods. " + EXAMPLES),
)
GREETING = re.compile(r"^\s*(hi+|hello+|hey+|hola|namaste|good (morning|afternoon|evening)|yo|sup|howdy)\b[\s!.,?]*(there|coach)?[\s!.,?]*$")
THANKS = re.compile(r"^\s*(thanks|thank you|thx|ty|cool|ok|okay|great|nice|got it|awesome)\b[\s!.,?]*$")
GREETING_REPLY = "Hi! I am your fitness coach. I can tell you about the calories, protein and portions in foods. " + EXAMPLES
THANKS_REPLY = "You are welcome! Ask me about any food whenever you like."


def nothing_fits_reply(message: str) -> str:
    """The reply for a message no specialist took. Always fixed text, chosen by simple patterns."""
    text = " ".join(message.lower().split())
    if GREETING.match(text):
        return GREETING_REPLY
    if THANKS.match(text):
        return THANKS_REPLY
    for _, pattern, reply in TOPICS:
        if pattern.search(text):
            return reply
    return NOTHING_FITS
