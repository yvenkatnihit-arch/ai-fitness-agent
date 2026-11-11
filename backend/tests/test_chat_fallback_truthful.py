"""Step 8.8 (D-114): the fallback replies must describe what the chat REALLY does today (they said "foods only" and "logging is on its screen"
long after that stopped being true). Offline."""

from app.agents.fallback import GREETING_REPLY, NOTHING_FITS, THANKS_REPLY, TOPICS, nothing_fits_reply
from app.agents.menu import default_menu


def test_no_reply_still_claims_the_chat_is_only_about_foods_or_cannot_log_meals():
    for reply in [NOTHING_FITS, GREETING_REPLY, THANKS_REPLY, *(r for _, _, r in TOPICS)]:
        assert "for now" not in reply and "only about foods" not in reply and "questions about foods. " not in reply
    logging = next(r for name, _, r in TOPICS if name == "logging")
    assert "tell me what you ate" in logging and "you confirm it" in logging          # chat can log a meal (with confirmation)


def test_the_generic_reply_names_every_specialist_the_menu_really_has():
    skills = {"nutrition": "nutrition", "exercises": "exercises", "my_plan": "your own plan", "meal_logger": "logging a meal"}
    assert set(default_menu()) == set(skills)                                         # a new specialist must be added to this reply too
    for phrase in skills.values():
        assert phrase in NOTHING_FITS


def test_a_weight_pace_question_the_router_declines_gets_a_helpful_pointer():
    reply = nothing_fits_reply("am I losing weight fast enough")
    assert "Home screen" in reply and "weight progress" in reply
