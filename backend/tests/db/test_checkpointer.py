"""D-012: does LangGraph's Postgres checkpointer work through our Supabase Session pooler?"""

import operator
import uuid
from typing import Annotated, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import SCHEMA, checkpointer, setup_checkpointer_tables

pytestmark = pytest.mark.db

LANGGRAPH_TABLES = {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}


class CounterState(TypedDict):
    count: int
    steps: Annotated[list[str], operator.add]  # a reducer, like agent_results in the chat graph


def add_one(state: CounterState) -> dict:
    return {"count": state["count"] + 1, "steps": ["add_one"]}


def build_graph(saver):
    graph = StateGraph(CounterState)
    graph.add_node("add_one", add_one)
    graph.add_edge(START, "add_one")
    graph.add_edge("add_one", END)
    return graph.compile(checkpointer=saver)


@pytest.fixture
def thread():
    """A fresh thread id; its checkpoints are deleted afterwards."""
    thread_id = f"test-{uuid.uuid4()}"
    yield {"configurable": {"thread_id": thread_id}}
    with checkpointer() as saver:
        saver.delete_thread(thread_id)


def test_tables_live_in_the_private_schema(admin_conn):
    setup_checkpointer_tables()  # idempotent: safe even though migrate.py already ran it
    rows = admin_conn.execute(
        "select table_schema, table_name from information_schema.tables where table_name = any(%s)",
        (list(LANGGRAPH_TABLES),),
    ).fetchall()
    assert {(SCHEMA, name) for name in LANGGRAPH_TABLES} == set(rows)  # and none in public


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_user_roles_cannot_use_the_schema(admin_conn, role):
    assert admin_conn.execute(
        "select has_schema_privilege(%s, %s, 'usage')", (role, SCHEMA)
    ).fetchone() == (False,)


def test_state_survives_a_new_connection(thread):
    with checkpointer() as saver:
        result = build_graph(saver).invoke({"count": 0, "steps": []}, thread)
    assert result["count"] == 1

    # A brand-new connection (like after a server restart) sees the saved state.
    with checkpointer() as saver:
        state = build_graph(saver).get_state(thread)
    assert state.values == {"count": 1, "steps": ["add_one"]}


def test_many_runs_on_one_connection(thread):
    # psycopg switches to prepared statements after a few repeats of the same query.
    # That breaks on a transaction pooler; on the session pooler it must keep working.
    with checkpointer() as saver:
        graph = build_graph(saver)
        for _ in range(12):
            graph.invoke({"count": 0, "steps": []}, thread)
        history = list(graph.get_state_history(thread))
    assert len(history) >= 12


def test_delete_thread_removes_its_state(thread):
    with checkpointer() as saver:
        graph = build_graph(saver)
        graph.invoke({"count": 0, "steps": []}, thread)
        saver.delete_thread(thread["configurable"]["thread_id"])
        assert graph.get_state(thread).values == {}
