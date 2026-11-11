"""The chat graph for ONE user message (Step 7.3, D-075): route -> spawn the needed specialists in parallel -> finish.

route:       the router picks specialists from the menu.
specialist:  runs once per assignment, all at the same time (LangGraph's Send API). Each run builds a fresh specialist with the
             factory (D-073), runs it, and drops it. Results are merged into one list.
finish:      one result -> its answer is the reply (no extra LLM call: the composer is skipped, a cost rule). Several -> the
             composer (D-076) merges them; if it fails its number check or the LLM errors, the answers are simply joined in order.
             None -> a friendly "what I can help with" message.
"""

import logging
import operator
from collections.abc import Callable
from typing import Annotated, Any, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt

from app.agents.approvals import APPROVE, REJECT, Decide, decide_with_workflow
from app.agents.composer import compose
from app.agents.claims import settle_answer
from app.agents.context import RunContext
from app.agents.fallback import NOTHING_FITS, nothing_fits_reply  # noqa: F401  (NOTHING_FITS is re-exported: tests and callers import it from here)
from app.agents.gemini_model import gemini_model
from app.agents.menu import Menu, default_menu
from app.agents.router import Assignment, route_message
from app.agents.runner import Model, ToolRecord, build_specialist
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry
from app.llm.client import LLMBusy, LLMFailed
from app.safety.guards import check_input, check_output

logger = logging.getLogger(__name__)

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
    history: list[tuple[str, str]]   # the last few messages before this one (role, text): context for the router only
    summary: str                     # the rolling summary of older messages
    assignments: list[Assignment]
    results: Annotated[list[SpecialistOutcome], operator.add]   # every parallel branch appends here
    reply: str
    composed: bool
    blocked: str   # set when a guard stopped the message or replaced the reply: the category (never the text)
    to_decide: list[dict[str, str]]   # pending proposals this run created, still waiting for the user: {"id", "summary"}
    decisions: Annotated[list[dict[str, str]], operator.add]


def build_chat_graph(*, menu: Menu | None = None, router: Router | None = None, make_model: ModelFactory | None = None,
                     composer: Composer | None = None, checkpointer: Any | None = None, decide: Decide | None = None) -> Any:
    """Compile the graph. Tests pass a fake router and fake models; production uses the real ones.
    `checkpointer` (needed to pause for approvals) saves the state between the question and the answer."""
    menu = menu if menu is not None else default_menu()
    decide = decide or decide_with_workflow

    def guard_in(state: ChatState) -> dict[str, Any]:
        """The input guard (D-078): code only, before any model. A blocked message gets a fixed reply and nothing else runs."""
        verdict = check_input(state["message"])
        if verdict is None:
            return {}
        logger.warning("input guard blocked a message (category=%s)", verdict.category)   # the category only, never the text
        return {"blocked": verdict.category, "reply": verdict.reply, "assignments": [], "to_decide": [], "composed": False}

    def route(state: ChatState) -> dict[str, Any]:
        uid = UUID(state["user_id"])
        picked = (router(state["message"]) if router
                  else route_message(state["message"], menu, user_id=uid, history=state.get("history", ()), summary=state.get("summary", "")))
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
        can_propose = any(registry.get(name).scope == "propose" for name in entry.spec.tools)
        answer = settle_answer(can_propose, any(t.proposal_id for t in r.tools), r.answer)   # words about a proposal come from code (D-109)
        return {"results": [SpecialistOutcome(specialist=r.specialist, status=r.status, answer=answer, steps=r.steps,
                                              tokens=r.tokens, tools=r.tools)]}

    def finish(state: ChatState) -> dict[str, Any]:
        out = _reply(state)
        unsafe = check_output(out["reply"])   # the output guard (D-078): a banned or unsafe reply is replaced, never shown
        if unsafe:
            logger.warning("output guard replaced a reply (category=%s)", unsafe.category)
            out = {"reply": unsafe.reply, "composed": False, "blocked": unsafe.category}
        pending = [{"id": t.proposal_id, "summary": t.proposal_summary} for r in state.get("results", []) for t in r["tools"]
                   if t.proposal_id]
        return {**out, "to_decide": pending}

    def _reply(state: ChatState) -> dict[str, Any]:
        order = {a.specialist: i for i, a in enumerate(state.get("assignments", []))}   # branches finish in any order
        done = sorted(state.get("results", []), key=lambda r: order.get(r["specialist"], 99))
        good = [(r["specialist"], r["answer"]) for r in done if r["status"] == "ok" and r["answer"]]
        answers = [a for _, a in good]
        if not state.get("assignments"):
            return {"reply": nothing_fits_reply(state["message"])}
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

    def after_finish(state: ChatState) -> str:
        # With no checkpointer the graph cannot pause, so proposals simply stay pending for the plan screen.
        return "approval" if checkpointer is not None and state.get("to_decide") else END

    def approval(state: ChatState) -> dict[str, Any]:
        """Ask the user about ONE proposal, then apply their answer. One per run of this node: LangGraph re-runs a node from the
        top when it resumes, so deciding several here would apply the first one twice. The loop is the edge back to this node."""
        item, rest = state["to_decide"][0], state["to_decide"][1:]
        answer = interrupt({"kind": "approve_proposal", "proposal_id": item["id"], "summary": item["summary"]})
        choice = answer if answer in (APPROVE, REJECT) else "leave"   # anything else changes nothing
        message = decide(UUID(state["user_id"]), UUID(item["id"]), choice)   # the id comes from OUR state, never from the answer
        return {"to_decide": rest, "decisions": [{"proposal_id": item["id"], "choice": choice, "message": message}]}

    graph = StateGraph(ChatState)
    graph.add_node("route", route)
    graph.add_node("specialist", specialist)
    graph.add_node("finish", finish)
    graph.add_node("approval", approval)
    graph.add_node("guard_in", guard_in)
    graph.add_edge(START, "guard_in")
    graph.add_conditional_edges("guard_in", lambda s: END if s.get("blocked") else "route", ["route", END])
    graph.add_conditional_edges("route", spawn, ["specialist", "finish"])
    graph.add_edge("specialist", "finish")
    graph.add_conditional_edges("finish", after_finish, ["approval", END])
    graph.add_conditional_edges("approval", lambda s: "approval" if s.get("to_decide") else END, ["approval", END])
    return graph.compile(checkpointer=checkpointer)


def _config(user_id: UUID, conversation_id: str) -> dict[str, Any]:
    """The thread id contains the user's id, so one user can never resume another user's paused conversation."""
    return {"configurable": {"thread_id": f"{user_id}:{conversation_id}"}}


def _summary(final: dict[str, Any]) -> dict[str, Any]:
    paused = [i.value for i in final.get("__interrupt__", [])]
    return {"reply": final.get("reply", ""), "assignments": final.get("assignments", []), "results": final.get("results", []),
            "composed": final.get("composed", False), "decisions": final.get("decisions", []), "blocked": final.get("blocked"),
            "waiting_for": paused[0] if paused else None}   # the card to show the user, or None when nothing is waiting


def answer_message(message: str, user_id: UUID, *, conversation_id: str | None = None, history: list[tuple[str, str]] | None = None,
                   summary: str = "", **kwargs: Any) -> dict[str, Any]:
    """Run the graph for one message. Returns the reply, what ran (for the 'How this was made' panel) and, when a proposal is
    waiting for the user, `waiting_for` (needs a `checkpointer` and a `conversation_id`; then call `resume_chat`)."""
    graph = build_chat_graph(**kwargs)
    state = {"message": message, "user_id": str(user_id), "results": [], "decisions": [], "history": history or [], "summary": summary}
    config = _config(user_id, conversation_id or str(uuid4()))
    return _summary(graph.invoke(state, config))


def resume_chat(user_id: UUID, conversation_id: str, choice: str, **kwargs: Any) -> dict[str, Any]:
    """Give the paused conversation the user's answer ("approve" or "reject"). Build the graph with the same options as before."""
    graph = build_chat_graph(**kwargs)
    # LangGraph itself crashes on Command(resume=None), so "no answer" is sent as an empty string (which changes nothing).
    return _summary(graph.invoke(Command(resume="" if choice is None else choice), _config(user_id, conversation_id)))


def waiting_card(user_id: UUID, conversation_id: str, **kwargs: Any) -> dict[str, Any] | None:
    """The proposal card this conversation is paused on, or None. Lets an endpoint refuse an answer when nothing is waiting."""
    state = build_chat_graph(**kwargs).get_state(_config(user_id, conversation_id))
    cards = [i.value for task in state.tasks for i in task.interrupts]
    return cards[0] if cards else None
