"""The small tier must not spend its output budget on hidden "thinking" tokens (found in Step 7.4: a reply was cut mid-sentence)."""

from app.llm.client import build_chat_model


def test_the_small_tier_has_thinking_switched_off():
    assert build_chat_model("small", 400).thinking_budget == 0


def test_the_mid_tier_keeps_the_models_default_thinking():
    assert build_chat_model("mid", 4000).thinking_budget is None
