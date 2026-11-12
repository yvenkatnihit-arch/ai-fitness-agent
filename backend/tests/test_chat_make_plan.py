"""Asking the chat to MAKE a plan is answered by code with a pointer to the plan screens (D-119); questions about a plan still go on."""
import pytest

from app.agents.fallback import MAKE_PLAN_REPLY, asks_for_a_plan, nothing_fits_reply

ASKS = ["make plan for me", "prepare a diet for me", "i want a diet for muscle building", "Create a 7 day meal plan", "build me a workout plan",
        "give me a diet plan for weight loss", "i need a workout routine", "generate a meal plan please"]
QUESTIONS = ["what is in my meal plan today", "what workout do I have on friday", "how much protein is in paneer", "do I need to change my plan",
             "what is my calorie target", "I ate 2 rotis and dal", "how do I do a plank"]


@pytest.mark.parametrize("text", ASKS)
def test_plan_requests_get_the_pointer_to_the_plan_screens(text):
    assert asks_for_a_plan(text)
    reply = nothing_fits_reply(text)
    assert "cannot" in reply and ("screen" in reply or "Workout" in reply)       # says it cannot, and which screen does it
    assert "Meal plan screen" in MAKE_PLAN_REPLY and "Workout plan screen" in MAKE_PLAN_REPLY


def test_an_unclear_request_names_both_screens():
    assert nothing_fits_reply("make plan for me") == MAKE_PLAN_REPLY


@pytest.mark.parametrize("text", QUESTIONS)
def test_questions_about_a_plan_are_not_taken(text):
    assert not asks_for_a_plan(text)
