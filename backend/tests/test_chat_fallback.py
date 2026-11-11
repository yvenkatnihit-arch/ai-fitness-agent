"""Step 7.11g (D-102): the reply when no specialist fits depends on the topic, is fixed text, and is always safe. Offline."""

from uuid import uuid4

import pytest

from app.agents import chat_graph
from app.agents.fallback import GREETING_REPLY, NOTHING_FITS, THANKS_REPLY, TOPICS, nothing_fits_reply
from app.safety.guards import check_output

TOPIC_REPLY = {name: reply for name, _, reply in TOPICS}


@pytest.mark.parametrize("message", ["hello", "Hi!", "hey there", "Good morning", "namaste", "  HELLO   coach "])
def test_greetings_get_a_greeting(message):
    assert nothing_fits_reply(message) == GREETING_REPLY


@pytest.mark.parametrize("message", ["thanks!", "Thank you", "ok", "cool", "got it"])
def test_thanks_get_a_short_reply(message):
    assert nothing_fits_reply(message) == THANKS_REPLY


@pytest.mark.parametrize("message, topic", [
    ("make me a workout plan", "workout"), ("how do I do a proper squat", "workout"), ("swap my bench press", "workout"),
    ("make me a 7 day meal plan", "meal_plan"), ("what should I eat today", "meal_plan"), ("any dinner ideas?", "meal_plan"),
    ("I ate 2 idlis for breakfast", "logging"), ("how do I log my lunch", "logging"),
    ("what's my calorie target", "targets"), ("I want to lose weight", "targets"), ("how is my progress", "targets"),
    ("change my diet to vegan", "settings"), ("update my profile", "settings"),
])
def test_each_topic_points_to_the_right_screen(message, topic):
    reply = nothing_fits_reply(message)
    assert reply == TOPIC_REPLY[topic]
    assert {"workout": "Workout plan", "meal_plan": "Meal plan", "logging": "Log a meal", "targets": "Home screen", "settings": "Settings"}[topic] in reply


@pytest.mark.parametrize("message", ["what is the capital of France", "tell me a joke", "asdf", "", "and that?"])
def test_anything_else_gets_the_generic_reply(message):
    assert nothing_fits_reply(message) == NOTHING_FITS


def test_different_questions_no_longer_all_get_the_same_reply():
    replies = {nothing_fits_reply(m) for m in ["hello", "make me a workout plan", "what should I eat today", "I ate dal", "what's my target", "tell me a joke"]}
    assert len(replies) == 6


def test_every_fixed_reply_passes_the_output_guard_and_never_repeats_the_users_words():
    for reply in [NOTHING_FITS, GREETING_REPLY, THANKS_REPLY, *TOPIC_REPLY.values()]:
        assert check_output(reply) is None and len(reply) < 400
    assert "zebra" not in nothing_fits_reply("make me a zebra workout")                  # nothing the user typed is echoed back


def test_the_chat_graph_uses_it_when_the_router_picks_nobody():
    out = chat_graph.answer_message("make me a workout plan", uuid4(), router=lambda m: [])
    assert out["reply"] == TOPIC_REPLY["workout"] and out["results"] == [] and out["assignments"] == []
    assert chat_graph.answer_message("hello", uuid4(), router=lambda m: [])["reply"] == GREETING_REPLY


def test_the_old_import_path_still_works():
    assert chat_graph.NOTHING_FITS == NOTHING_FITS
