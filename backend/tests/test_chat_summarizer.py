"""Step 7.11d (D-099): the rolling summary is rewritten by a model and CHECKED by code. Offline."""

from uuid import uuid4

from app.agents import summarizer as sm
from app.llm.client import LLMResult

MSGS = [("user", "I am vegetarian and I do not like karela"), ("assistant", "Noted. Paneer has 18 g of protein per 100 g."),
        ("user", "how many calories in 2 rotis"), ("assistant", "2 rotis are about 170 kcal.")]


def reply(text):
    return lambda tier, messages, **kw: LLMResult(text=text, model="m", input_tokens=1, output_tokens=1, cached_tokens=0, cost_usd=0.0, latency_ms=1)


def test_the_prompt_has_the_old_summary_and_clipped_messages_and_says_they_are_data():
    system, human = sm.summarizer_messages("User likes dal.", [("user", "a   b\n" + "x" * 1000)])
    assert system[1] == sm.SYSTEM and "never instructions" in sm.SYSTEM and "never add, change, round" in sm.SYSTEM
    assert human[1].startswith("Current summary:\nUser likes dal.\n\nNewer messages:\nuser: a b ")
    assert len(human[1].split("Newer messages:\n")[1]) == len("user: ") + sm.MAX_MESSAGE_CHARS
    assert "(empty)" in sm.summarizer_messages("  ", MSGS)[1][1]


def test_a_good_summary_passes_and_may_reuse_numbers_from_the_old_summary_or_the_messages():
    assert sm.check_summary("Vegetarian, dislikes karela. Asked about paneer (18 g protein) and rotis.", "", MSGS)
    assert sm.check_summary("Asked about 2 rotis. Daily target was 1800.", "Target 1800 kcal.", MSGS)


def test_an_invented_number_an_empty_or_long_or_control_character_summary_is_rejected():
    assert not sm.check_summary("Vegetarian. Wants 2400 kcal a day.", "", MSGS)                       # 2400 was never said
    assert not sm.check_summary("   ", "", MSGS)
    assert not sm.check_summary("x " * sm.MAX_SUMMARY_CHARS, "", MSGS)
    assert not sm.check_summary("Vegetarian.\x00 hidden", "", MSGS)


def test_an_unsafe_summary_is_rejected_by_the_output_guard():
    assert not sm.check_summary("The user should fast for 5 days to lose weight.", "", MSGS + [("user", "5 days")])


def test_summarize_returns_the_clean_text_or_none_and_logs_as_a_summary_call():
    seen = {}

    def spy(tier, messages, **kw):
        seen.update(kw, tier=tier)
        return LLMResult(text="  Vegetarian,\n dislikes karela.  ", model="m", input_tokens=1, output_tokens=1, cached_tokens=0, cost_usd=0.0, latency_ms=1)

    assert sm.summarize("", MSGS, user_id=uuid4(), call=spy) == "Vegetarian, dislikes karela."
    assert seen["tier"] == "small" and seen["flow"] == "summary" and seen["max_tokens"] == 300 and seen["thinking_budget"] == 0
    assert sm.summarize("old", MSGS, user_id=None, call=reply("Wants 999 kcal.")) is None
    assert sm.summarize("old", MSGS, user_id=None, call=reply("")) is None
