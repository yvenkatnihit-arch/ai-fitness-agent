"""Step 8.5 (D-109): a specialist that can propose never claims more than happened. Offline."""

from uuid import uuid4

import pytest

from app.agents import chat_graph
from app.agents.claims import COULD_NOT_PREPARE, PREPARED, settle_answer
from app.agents.menu import MenuEntry
from app.agents.router import Assignment
from app.agents.runner import ToolCall, Turn
from app.agents.spec import SpecialistSpec
from app.agents.tools import Tool, ToolRegistry
from pydantic import BaseModel, ConfigDict


@pytest.mark.parametrize("answer", ["I prepared a meal log for lunch. Please confirm it.", "Your meal has been logged!", "Done, I saved it.",
                                    "I added 2 rotis to your lunch.", "Recorded. Please confirm this."])
def test_a_claim_of_success_without_a_proposal_is_replaced_by_an_honest_message(answer):
    assert settle_answer(True, False, answer) == COULD_NOT_PREPARE


@pytest.mark.parametrize("answer", ["What meal was that?", "How many rotis did you have?", "Can you confirm the amount?", "Which day, today or yesterday?"])
def test_a_clarifying_question_is_left_alone(answer):
    assert settle_answer(True, False, answer) == answer


def test_when_a_proposal_exists_the_words_come_from_code_whatever_the_model_said():
    for said in ("I prepared it.", "Done! Your meal is saved and logged.", "random words", ""):
        assert settle_answer(True, True, said) == PREPARED
    assert "save it" in PREPARED and "Approve" in PREPARED and "has been saved" not in PREPARED     # it says save only as what Approve will do


def test_an_answer_with_no_claim_and_no_proposal_is_unchanged():
    assert settle_answer(True, False, "I need to know the amount. Say it like: 2 rotis.") == "I need to know the amount. Say it like: 2 rotis."


def test_specialists_that_cannot_propose_are_never_touched():
    for said in ("Paneer has 18 g of protein. I saved nothing.", "I have logged 2 days this week.", None):
        assert settle_answer(False, False, said) == said and settle_answer(False, True, said) == said


# ---------- in the graph ----------

class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def logger_menu(proposal_id):
    tool = Tool("propose_it", "propose", NoArgs, lambda c, a: ({"proposal_id": proposal_id, "summary": "Log lunch"} if proposal_id else {"error": "bad"}), scope="propose")

    def registry():
        r = ToolRegistry()
        r.register(tool)
        return r
    return {"logger": MenuEntry(SpecialistSpec(name="logger", system_prompt="p", tools=frozenset({"propose_it"})), registry, "x")}


def run(proposal_id, final):
    turns = iter([Turn(call=ToolCall("propose_it", {})), Turn(final=final)])
    return chat_graph.answer_message("I ate rotis", uuid4(), menu=logger_menu(proposal_id), router=lambda m: [Assignment("logger", "log it")],
                                     make_model=lambda s, r: (lambda m: next(turns)), composer=lambda m, a: None)


def test_in_the_graph_a_failed_proposal_with_a_confident_model_gives_the_honest_message():
    assert run(None, "I prepared your meal log. Please confirm it.")["reply"] == COULD_NOT_PREPARE


def test_in_the_graph_a_real_proposal_gives_the_fixed_text_and_the_card_data():
    out = run(str(uuid4()), "All saved and logged!")
    assert out["reply"] == PREPARED and out["results"][0]["tools"][0].proposal_id
