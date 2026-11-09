"""The chat graph for ONE user message (Step 7.3, D-075): route -> spawn the needed specialists in parallel -> finish.

route:       the router picks specialists from the menu.
specialist:  runs once per assignment, all at the same time (LangGraph's Send API). Each run builds a fresh specialist with the
             factory (D-073), runs it, and drops it. Results are merged into one list.
finish:      one result -> its answer is the reply (no extra LLM call: the composer is skipped, a cost rule). Several -> the
             composer (D-076) merges them; if it fails its number check or the LLM errors, the answers are simply joined in order.
             None -> a friendly "what I can help with" message.
"""

import operator
from collections.abc import Callable
from typing import Annotated, Any, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.context import RunContext
from app.agents.gemini_model import gemini_model
from app.agents.composer import compose
from app.agents.menu import Menu, default_menu
from app.agents.router import Assignment, route_message
from app.agents.runner import Model, ToolRecord, build_specialist
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry
from app.llm.client import LLMBusy, LLMFailed

NOTHING_FITS = ("I can help with questions about foods and dishes for now, such as calories, protein and portion sizes. "
                "What would you like to know?")
SPECIALIST_FAILED = "I could not finish that one. Please try again."

Router = Callable[[str], list[Assignment]]
Composer = Callable[[str, list[tuple[str, str]]], str | None]   # (user message, [(specialist, answer)]) -> merged reply or None
ModelFactory = Callable[[SpecialistSpec, ToolRegistry], Model]


class SpecialistOutcome(TypedDict):
    specialist: str
    status: str
    answer: str | None
    steps: int
    tokens: int
    tools: list[ToolRecord]


class ChatState(TypedDict, total=False):
    message: str
    user_id: str
    assignments: list[Assignment]
    results: Annotated[list[SpecialistOutcome], operator.add]   # every parallel branch appends here
    reply: str
    composed: bool


def build_chat_graph(*, menu: Menu | None = None, router: Router | None = None, make_model: ModelFactory | None = None,
                     composer: Composer | None = None) -> Any:
    """Compile the graph. Tests pass a fake router and fake models; production uses the real ones."""
    menu = menu if menu is not None else default_menu()

    def route(state: ChatState) -> dict[str, Any]:
        uid = UUID(state["user_id"])
        picked = router(state["message"]) if router else route_message(state["message"], menu, user_id=uid)
        return {"assignments": [a for a in picked if a.specialist in menu]}   # the menu is the only authority

    def spawn(state: ChatState) -> list[Send] | str:
        sends = [Send("specialist", {"user_id": state["user_id"], "assignment": a}) for a in state.get("assignments", [])]
        return sends or "finish"

    def specialist(payload: dict[str, Any]) -> dict[str, Any]:
        assignment: Assignment = payload["assignment"]
        user_id = UUID(payload["user_id"])
        entry = menu[assignment.specialist]
        registry = entry.registry()
        brain = make_model(entry.spec, registry) if make_model else gemini_model(entry.spec, registry, user_id=user_id, flow="chat")
        r = build_specialist(entry.spec, registry, brain).run(assignment.task, RunContext(user_id))
        return {"results": [SpecialistOutcome(specialist=r.specialist, status=r.status, answer=r.answer, steps=r.steps,
                                              tokens=r.tokens, tools=r.tools)]}

    def finish(state: ChatState) -> dict[str, Any]:
        order = {a.specialist: i for i, a in enumerate(state.get("assignments", []))}   # branches finish in any order
        done = sorted(state.get("results", []), key=lambda r: order.get(r["specialist"], 99))
        good = [(r["specialist"], r["answer"]) for r in done if r["status"] == "ok" and r["answer"]]
        answers = [a for _, a in good]
        if not state.get("assignments"):
            return {"reply": NOTHING_FITS}
        if not answers:
            return {"reply": SPECIALIST_FAILED}
        if len(answers) == 1:
            return {"reply": answers[0], "composed": False}
        merged = None
        try:
            merged = (composer(state["message"], good) if composer
                      else compose(state["message"], good, user_id=UUID(state["user_id"])))
        except (LLMBusy, LLMFailed):
            pass   # fall back to the joined answers
        return {"reply": merged or "\n\n".join(answers), "composed": merged is not None}

    graph = StateGraph(ChatState)
    graph.add_node("route", route)
    graph.add_node("specialist", specialist)
    graph.add_node("finish", finish)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", spawn, ["specialist", "finish"])
    graph.add_edge("specialist", "finish")
    graph.add_edge("finish", END)
    return graph.compile()


def answer_message(message: str, user_id: UUID, **kwargs: Any) -> dict[str, Any]:
    """Run the graph for one message. Returns the reply plus what ran (for the 'How this was made' panel)."""
    final = build_chat_graph(**kwargs).invoke({"message": message, "user_id": str(user_id), "results": []})
    return {"reply": final["reply"], "assignments": final.get("assignments", []), "results": final.get("results", []),
            "composed": final.get("composed", False)}
